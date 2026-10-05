"""The coach writing first. A pattern the record just made visible, or a
follow-up the person agreed to, becomes one coach message in the family's
thread and then a notification pointing at it. Kept rare on purpose: one
unanswered message at a time, a budget from the person's own setting, and a
kind of message ignored twice in a row stops until they answer."""

import datetime
import enum
import re
from zoneinfo import ZoneInfo

from pywebpush import WebPushException

from btcopilot import clock, correlation, prompts, push
from btcopilot.discussions import chats, sitting, sync_chat_speakers
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import (
    Diagram,
    Discussion,
    Notification,
    Observation,
    ObservationKind,
    ProactiveMessage,
    ProductEvent,
    Purpose,
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
# Two events are set side by side as nearness in time, never as one causing the other.
CAUSES = (
    "led to",
    "leads to",
    "caused",
    "causes",
    "because",
    "triggered",
    "resulted in",
    "due to",
    "made you",
)
CAUSE = re.compile(r"\b(" + "|".join(CAUSES) + r")\b", re.IGNORECASE)
REPLIED_WITHIN = datetime.timedelta(hours=48)
RETURNED_WITHIN = datetime.timedelta(days=7)
# How long after sending the loop's counts are still looked for.
COUNTED_FOR = datetime.timedelta(days=14)
# Where the meeting is: the coders' reminders wait for the day there. The
# coach's own messages wait for the day where the person is (users.timezone).
ZONE = ZoneInfo("America/Anchorage")
HOURS = range(9, 20)
# Words that broke the shape this many times for one pattern end its tries.
TRIES = 3
# How often a message the person did not ask for may come, by their setting.
BUDGET = {
    Proactive.Weekly: datetime.timedelta(days=7),
    Proactive.Rarely: datetime.timedelta(days=30),
}


class Reason(enum.StrEnum):
    """Why nothing went to a person on a run, as the run prints it."""

    Night = (
        f"outside sending hours, {HOURS.start}:00 to {HOURS.stop - 1}:59 where the "
        "person is"
    )
    Waiting = "the last message is still waiting for an answer"
    Ignored = "the last two of its kind went unanswered; it waits for a reply"
    Off = "preference off: the person chose never"
    Budget = "over budget: the last message they did not ask for is too recent for their setting"
    Quiet = "no new pattern in the record to write about"


class Unsendable(ValueError):
    """The model's words broke the shape a first message must have: at most
    two sentences, the last a question, and no word making one event the
    cause of the other."""


def zone_of(user: User) -> datetime.tzinfo:
    """Where the person is: the zone the page last sent with a message, kept
    on their row; UTC until a message has carried one (R-0758)."""
    name = clock.zone(user.timezone)
    return ZoneInfo(name) if name else clock.UTC


def ask_later(user_id: int, diagram_id: int, when: datetime.date, question: str):
    """The question waits for the morning of that day where the person is."""
    zone = zone_of(db.session.get(User, user_id))
    message = ProactiveMessage(
        user_id=user_id,
        diagram_id=diagram_id,
        trigger=Trigger.FollowUp,
        question=question,
        due_at=_utc(datetime.datetime.combine(when, datetime.time(HOURS.start), zone)),
    )
    db.session.add(message)
    return message


def run(now: datetime.datetime | None = None, dry_run: bool = False) -> list[dict]:
    """At most one message per person per run, and only in their day. Each
    person gets a row: the words written, or the reason none were. A dry run
    keeps nothing and sends nothing, and stops before the model: a pattern
    becomes a row saying the words would be written about it."""
    now = now or datetime.datetime.utcnow()
    rows = []
    asked = _asked()
    for user in User.query.order_by(User.id):
        if user.id not in asked and user.pref(PrefKey.Proactive) is Proactive.Never:
            found = Reason.Off
        else:
            _answers(user, now)
            found = _pick(user, now) if daytime(now, zone_of(user)) else Reason.Night
        if isinstance(found, Reason):
            rows.append(_row(user, reason=found.value))
            continue
        if dry_run and isinstance(found, correlation.Firing):
            rows.append(
                _row(
                    user,
                    Trigger.Correlation,
                    f"would write about {found.key}",
                    refused=False,
                )
            )
            continue
        message, text, refused = _compose(user, found)
        row = _row(user, message.trigger, text, refused)
        rows.append(row)
        if dry_run or refused:
            continue
        # a send the push service refuses leaves the message unsent for the
        # next run rather than in the thread with no notification
        try:
            with db.session.begin_nested():
                _send(user, message, text, now)
        except WebPushException as e:
            row["reason"] = push.failure(e)
            continue
        db.session.commit()
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return rows


def _row(
    user: User,
    trigger: Trigger | None = None,
    text: str | None = None,
    refused: bool | None = None,
    reason: str | None = None,
) -> dict:
    return {
        "email": user.username,
        "trigger": trigger.value if trigger else None,
        "text": text,
        "refused": refused,
        "reason": reason,
    }


def _utc(moment: datetime.datetime) -> datetime.datetime:
    return moment.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def daytime(moment: datetime.datetime, zone: datetime.tzinfo = ZONE) -> bool:
    return local(moment, zone).hour in HOURS


def local(moment: datetime.datetime, zone: datetime.tzinfo = ZONE) -> datetime.datetime:
    return moment.replace(tzinfo=datetime.timezone.utc).astimezone(zone)


def _asked() -> set[int]:
    """Everyone with a follow-up they agreed to still waiting to go."""
    return {
        user_id
        for (user_id,) in db.session.query(ProactiveMessage.user_id).filter(
            ProactiveMessage.trigger == Trigger.FollowUp,
            ProactiveMessage.sent_at.is_(None),
        )
    }


def _sent(user: User) -> list[ProactiveMessage]:
    return (
        ProactiveMessage.query.filter(
            ProactiveMessage.user_id == user.id, ProactiveMessage.sent_at.isnot(None)
        )
        .order_by(ProactiveMessage.sent_at)
        .all()
    )


def _ignored(message: ProactiveMessage, now: datetime.datetime) -> bool:
    return message.replied_at is None and now - message.sent_at > IGNORED_AFTER


def _pick(
    user: User, now: datetime.datetime
) -> ProactiveMessage | correlation.Firing | Reason:
    """A follow-up the person asked for comes before a pattern, and outside
    the budget; neither comes while the last message waits for an answer or
    after two of its kind in a row went unanswered."""
    sent = _sent(user)
    if sent and sent[-1].replied_at is None and not _ignored(sent[-1], now):
        return Reason.Waiting
    stopped = {t for t in Trigger if _stopped([m for m in sent if m.trigger is t], now)}
    due = (
        ProactiveMessage.query.filter(
            ProactiveMessage.user_id == user.id,
            ProactiveMessage.trigger == Trigger.FollowUp,
            ProactiveMessage.sent_at.is_(None),
            ProactiveMessage.due_at <= now,
        )
        .order_by(ProactiveMessage.due_at)
        .first()
    )
    if due and Trigger.FollowUp not in stopped:
        return due
    found = _unasked(user, sent, Trigger.Correlation in stopped, now)
    # a follow-up that was due and held back is the reason, over the pattern's
    return Reason.Ignored if due and isinstance(found, Reason) else found


def _stopped(sent: list[ProactiveMessage], now: datetime.datetime) -> bool:
    last = sent[-IGNORED_IN_A_ROW:]
    return len(last) == IGNORED_IN_A_ROW and all(_ignored(m, now) for m in last)


def _unasked(
    user: User, sent: list[ProactiveMessage], stopped: bool, now
) -> correlation.Firing | Reason:
    setting = user.pref(PrefKey.Proactive)
    if setting is Proactive.Never:
        return Reason.Off
    if stopped:
        return Reason.Ignored
    unasked = [m for m in sent if m.trigger is not Trigger.FollowUp]
    if unasked and now - unasked[-1].sent_at < BUDGET[setting]:
        return Reason.Budget
    return _pattern(user) or Reason.Quiet


def _pattern(user: User) -> correlation.Firing | None:
    """The newest pattern on the family the person is on that was neither
    sent nor out of tries."""
    diagram_id = user.diagram_in_use()
    if diagram_id is None:
        return None
    data = db.session.get(Diagram, diagram_id).get_diagram_data()
    written = {
        m.key
        for m in ProactiveMessage.query.filter_by(
            diagram_id=diagram_id, trigger=Trigger.Correlation
        )
        if m.sent_at or _counted(m, ObservationKind.ProactiveRefused) >= TRIES
    }
    events = {e["id"]: e for e in data.events}
    fresh = [f for f in correlation.firings(data) if f.key not in written]
    return max(
        fresh, key=lambda f: correlation.span(events[f.pairs[-1][1]]), default=None
    )


def _compose(user: User, found) -> tuple[ProactiveMessage, str, bool]:
    """Words that break the shape are kept unsent against the pattern and
    written down as a fault to tune each time; the pattern is asked of the
    model again on later runs until it has broken the shape TRIES times."""
    if isinstance(found, ProactiveMessage):
        return found, found.question, False
    diagram = db.session.get(Diagram, user.diagram_in_use())
    message = ProactiveMessage.query.filter_by(
        diagram_id=diagram.id, key=found.key
    ).one_or_none() or ProactiveMessage(
        user_id=user.id,
        diagram_id=diagram.id,
        trigger=Trigger.Correlation,
        key=found.key,
    )
    try:
        metered = Metered(
            user.id, diagram.id, f"proactive:{found.key}", Purpose.Proactive
        )
        return message, words(diagram.get_diagram_data(), found, metered), False
    except Unsendable as refused:
        db.session.add(message)
        db.session.flush()
        _count(message, ObservationKind.ProactiveRefused, {"text": str(refused)})
        return message, str(refused), True


def words(data: DiagramData, firing: correlation.Firing, metered: Metered) -> str:
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
    text = metered.text(
        prompts.proactive(events="\n".join(lines), speaker=data.subject_display_name())
    ).strip()
    if (
        not text.endswith("?")
        or len(SENTENCE_END.findall(text)) > MOST_SENTENCES
        or CAUSE.search(text)
    ):
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
    message.sent_at = now
    db.session.add(message)
    db.session.flush()
    _count(message, ObservationKind.ProactiveSent)
    push.send(user, statement)


def _answers(user: User, now: datetime.datetime):
    """Who answered, and the loop's counts: opened, replied within two days,
    back in the app within a week. Each is written once per message."""
    for message in _sent(user):
        if message.replied_at is None:
            message.replied_at = _reply(user, message)
        if now - message.sent_at > COUNTED_FOR:
            continue
        if (
            message.replied_at
            and message.replied_at - message.sent_at <= REPLIED_WITHIN
        ):
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
            Statement.speaker_id.in_(voices), Statement.created_at > message.sent_at
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
    until = message.sent_at + RETURNED_WITHIN
    if message.replied_at and message.replied_at <= until:
        return True
    return (
        ProductEvent.query.filter(
            ProductEvent.user_id == user.id,
            ProductEvent.created_at > message.sent_at,
            ProductEvent.created_at <= until,
        ).first()
        is not None
    )


def _counted(message: ProactiveMessage, kind: ObservationKind) -> int:
    return Observation.query.filter_by(
        turn_id=f"proactive-{message.id}", kind=kind
    ).count()


def _count(message: ProactiveMessage, kind: ObservationKind, detail=None):
    """Once per message and kind, but a refusal each time it happens."""
    if kind is not ObservationKind.ProactiveRefused and _counted(message, kind):
        return
    db.session.add(
        Observation(
            diagram_id=message.diagram_id,
            turn_id=f"proactive-{message.id}",
            kind=kind,
            detail={
                "reason": message.trigger.value,
                "message": message.id,
                **(detail or {}),
            },
        )
    )
