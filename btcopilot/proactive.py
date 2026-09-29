"""The coach writing first. A pattern the record just made visible, or a
follow-up the person agreed to, becomes one coach message in the family's
thread and then a notification pointing at it. Kept rare on purpose: one
unanswered message at a time, a budget from the person's own setting, and a
kind of message ignored twice in a row stops until they answer."""

import datetime
import re
from zoneinfo import ZoneInfo

from btcopilot import correlation, prompts, push
from btcopilot.discussions import chats, sitting, sync_chat_speakers
from btcopilot.extensions import db
from btcopilot.llmutil import response_text_sync
from btcopilot.models import (
    Diagram,
    Discussion,
    Notification,
    Observation,
    ObservationKind,
    ProactiveMessage,
    ProductEvent,
    Statement,
    StatementKind,
    Trigger,
    User,
)
from btcopilot.models.preferences import PrefKey, Proactive
from btcopilot.recordtext import event_line, person_line
from btcopilot.schema import DiagramData

TASK = "proactive_run"
# Unanswered this long, a message stops holding back the next and counts as ignored.
IGNORED_AFTER = datetime.timedelta(days=7)
IGNORED_IN_A_ROW = 2
MOST_SENTENCES = 2
SENTENCE_END = re.compile(r"[.?!]+(?=\s|$)")
REPLIED_WITHIN = datetime.timedelta(hours=48)
RETURNED_WITHIN = datetime.timedelta(days=7)
# How long after sending the loop's counts are still looked for.
COUNTED_FOR = datetime.timedelta(days=14)
# No one's time zone is kept yet, so every message waits for the day in one.
ZONE = ZoneInfo("America/Anchorage")
HOURS = range(9, 20)
# How often a message the person did not ask for may come, by their setting.
BUDGET = {
    Proactive.Weekly: datetime.timedelta(days=7),
    Proactive.Rarely: datetime.timedelta(days=30),
}


class Unsendable(ValueError):
    """The model's words broke the shape a first message must have: at most
    two sentences, the last a question."""


def ask_later(user_id: int, diagram_id: int, when: datetime.date, question: str):
    message = ProactiveMessage(
        user_id=user_id,
        diagram_id=diagram_id,
        trigger=Trigger.FollowUp,
        question=question,
        due_at=_utc(datetime.datetime.combine(when, datetime.time(HOURS.start), ZONE)),
    )
    db.session.add(message)
    return message


def run(now: datetime.datetime | None = None, dry_run: bool = False) -> list[dict]:
    """At most one message per person per run, and only in the day. A dry run
    keeps nothing and sends nothing, but the words are still asked of the
    model."""
    now = now or datetime.datetime.utcnow()
    said = []
    daytime = _local(now).hour in HOURS
    for user in _people():
        _answers(user, now)
        found = _pick(user, now) if daytime else None
        if found is None:
            continue
        message, text, refused = _compose(user, found)
        said.append(
            {
                "email": user.username,
                "trigger": message.trigger.value,
                "text": text,
                "refused": refused,
            }
        )
        if not dry_run and not refused:
            _send(user, message, text, now)
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return said


def _utc(moment: datetime.datetime) -> datetime.datetime:
    return moment.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def _local(moment: datetime.datetime) -> datetime.datetime:
    return moment.replace(tzinfo=datetime.timezone.utc).astimezone(ZONE)


def _people() -> list[User]:
    asked = {
        user_id
        for (user_id,) in db.session.query(ProactiveMessage.user_id).filter(
            ProactiveMessage.trigger == Trigger.FollowUp,
            ProactiveMessage.statement_id.is_(None),
        )
    }
    return [
        user
        for user in User.query.order_by(User.id)
        if user.id in asked or user.pref(PrefKey.Proactive) is not Proactive.Never
    ]


def _sent(user: User) -> list[ProactiveMessage]:
    return (
        ProactiveMessage.query.join(Statement)
        .filter(ProactiveMessage.user_id == user.id)
        .order_by(Statement.created_at)
        .all()
    )


def _at(message: ProactiveMessage) -> datetime.datetime:
    return message.statement.created_at


def _ignored(message: ProactiveMessage, now: datetime.datetime) -> bool:
    return message.replied_at is None and now - _at(message) > IGNORED_AFTER


def _pick(
    user: User, now: datetime.datetime
) -> ProactiveMessage | correlation.Firing | None:
    """A follow-up the person asked for comes before a pattern, and outside
    the budget; neither comes while the last message waits for an answer or
    after two of its kind in a row went unanswered."""
    sent = _sent(user)
    if sent and sent[-1].replied_at is None and not _ignored(sent[-1], now):
        return None
    stopped = {t for t in Trigger if _stopped([m for m in sent if m.trigger is t], now)}
    if Trigger.FollowUp not in stopped:
        due = (
            ProactiveMessage.query.filter(
                ProactiveMessage.user_id == user.id,
                ProactiveMessage.trigger == Trigger.FollowUp,
                ProactiveMessage.statement_id.is_(None),
                ProactiveMessage.due_at <= now,
            )
            .order_by(ProactiveMessage.due_at)
            .first()
        )
        if due:
            return due
    if Trigger.Correlation in stopped or not _allowed(user, sent, now):
        return None
    return _pattern(user)


def _stopped(sent: list[ProactiveMessage], now: datetime.datetime) -> bool:
    last = sent[-IGNORED_IN_A_ROW:]
    return len(last) == IGNORED_IN_A_ROW and all(_ignored(m, now) for m in last)


def _allowed(user: User, sent: list[ProactiveMessage], now) -> bool:
    setting = user.pref(PrefKey.Proactive)
    if setting is Proactive.Never:
        return False
    unasked = [m for m in sent if m.trigger is not Trigger.FollowUp]
    return not unasked or now - _at(unasked[-1]) >= BUDGET[setting]


def _pattern(user: User) -> correlation.Firing | None:
    """The newest pattern not yet written about on the family the person is on."""
    diagram_id = user.diagram_in_use()
    if diagram_id is None:
        return None
    data = db.session.get(Diagram, diagram_id).get_diagram_data()
    written = {
        key
        for (key,) in db.session.query(ProactiveMessage.key).filter(
            ProactiveMessage.diagram_id == diagram_id,
            ProactiveMessage.trigger == Trigger.Correlation,
        )
    }
    events = {e["id"]: e for e in data.events}
    fresh = [f for f in correlation.firings(data) if f.key not in written]
    return max(
        fresh, key=lambda f: correlation.span(events[f.pairs[-1][1]]), default=None
    )


def _compose(user: User, found) -> tuple[ProactiveMessage, str, bool]:
    """Words that break the shape are kept unsent against the pattern, so it
    is not asked of the model again, and written down as a fault to tune."""
    if isinstance(found, ProactiveMessage):
        return found, found.question, False
    diagram = db.session.get(Diagram, user.diagram_in_use())
    message = ProactiveMessage(
        user_id=user.id,
        diagram_id=diagram.id,
        trigger=Trigger.Correlation,
        key=found.key,
    )
    try:
        return message, words(diagram.get_diagram_data(), found), False
    except Unsendable as refused:
        db.session.add(message)
        db.session.flush()
        _count(message, ObservationKind.ProactiveRefused, {"text": str(refused)})
        return message, str(refused), True


def words(data: DiagramData, firing: correlation.Firing) -> str:
    """One short model call: the two events side by side, then a question."""
    events = {e["id"]: e for e in data.events}
    people = {p["id"]: p for p in data.people}
    speaker = (data.primary_person() or {}).get("id")
    *earlier, newest = firing.pairs
    involved = {firing.person} | {
        who
        for pair in firing.pairs
        for event_id in pair
        for who in _people_in(events[event_id])
    }
    lines = [
        "PEOPLE",
        *(person_line(people[i], i == speaker) for i in sorted(involved)),
        "EARLIER",
        *(event_line(events[i]) for pair in earlier for i in pair),
        "NEWEST",
        *(event_line(events[i]) for i in newest),
    ]
    text = response_text_sync(
        prompts.proactive(events="\n".join(lines), speaker=data.subject_display_name())
    ).strip()
    if not text.endswith("?") or len(SENTENCE_END.findall(text)) > MOST_SENTENCES:
        raise Unsendable(text)
    return text


def _people_in(event: dict) -> set[int]:
    found = {event.get(k) for k in ("person", "spouse", "child")}
    found.update(event.get("relationshipTargets") or [])
    found.discard(None)
    return found


def _send(user: User, message: ProactiveMessage, text: str, now):
    diagram = db.session.get(Diagram, message.diagram_id)
    discussion = sitting(user, diagram)
    statement = Statement(
        discussion_id=discussion.id,
        text=text,
        speaker=discussion.chat_ai_speaker,
        order=discussion.next_order(),
        kind=StatementKind.Turn,
        created_at=now,
    )
    db.session.add(statement)
    sync_chat_speakers(discussion)
    message.statement = statement
    db.session.add(message)
    db.session.flush()
    _count(message, ObservationKind.ProactiveSent)
    db.session.commit()
    push.send(user, statement)


def _answers(user: User, now: datetime.datetime):
    """Who answered, and the loop's counts: opened, replied within two days,
    back in the app within a week. Each is written once per message."""
    for message in _sent(user):
        if message.replied_at is None:
            message.replied_at = _reply(user, message)
        if now - _at(message) > COUNTED_FOR:
            continue
        if message.replied_at and message.replied_at - _at(message) <= REPLIED_WITHIN:
            _count(message, ObservationKind.ProactiveReplied)
        if _opened(message):
            _count(message, ObservationKind.ProactiveOpened)
        if _returned(user, message):
            _count(message, ObservationKind.ProactiveReturned)


def _reply(user: User, message: ProactiveMessage) -> datetime.datetime | None:
    voices = [
        speaker_id
        for (speaker_id,) in chats(user, message.diagram_id).with_entities(
            Discussion.chat_user_speaker_id
        )
    ]
    first = (
        Statement.query.filter(
            Statement.speaker_id.in_(voices), Statement.created_at > _at(message)
        )
        .order_by(Statement.created_at)
        .first()
    )
    return first.created_at if first else None


def _opened(message: ProactiveMessage) -> bool:
    return (
        Notification.query.filter(
            Notification.statement_id == message.statement_id,
            Notification.opened_at.isnot(None),
        ).first()
        is not None
    )


def _returned(user: User, message: ProactiveMessage) -> bool:
    until = _at(message) + RETURNED_WITHIN
    if message.replied_at and message.replied_at <= until:
        return True
    return (
        ProductEvent.query.filter(
            ProductEvent.user_id == user.id,
            ProductEvent.created_at > _at(message),
            ProductEvent.created_at <= until,
        ).first()
        is not None
    )


def _count(message: ProactiveMessage, kind: ObservationKind, detail=None):
    turn_id = f"proactive-{message.id}"
    if Observation.query.filter_by(turn_id=turn_id, kind=kind).first():
        return
    db.session.add(
        Observation(
            diagram_id=message.diagram_id,
            turn_id=turn_id,
            kind=kind,
            detail={
                "reason": message.trigger.value,
                "message": message.id,
                **(detail or {}),
            },
        )
    )
