"""The one door between the review and the chat app it reads.

Nothing else under btcopilot/review may import the app modules; the import
test in the review tests enforces it. Keeping the whole surface in one file
means the review can be read, moved or replaced without hunting for the places
it reached into the app.
"""

import datetime
import re
import uuid
from collections import Counter
from decimal import Decimal

from sqlalchemy import func

import btcopilot
from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot import observer, proactive, profile, prompts, push, record, turnstore
from btcopilot.record import Invalid
from btcopilot.coachmodel import COACH_EFFORT, CoachModel, model_for
from btcopilot.coachturn import CoachTurn
from btcopilot.discussions import utc_iso
from btcopilot.metered import Metered, OverCap
from btcopilot.models import (
    Author,
    Change,
    Discussion,
    DiscussionKind,
    ModelCall,
    Purpose,
    Speaker,
    SpeakerType,
    Statement,
    TurnEvent,
)
from btcopilot.recordtext import date_text, render, version_line
from btcopilot.toolnames import toolcall
from btcopilot.turnlog import TurnEventKind
from btcopilot.prompts import ToolText
from btcopilot.toolbox import (
    CERTAINTY,
    GONE,
    ToolError,
    Toolbox,
    ToolName,
    choice,
    report_schema,
)
from btcopilot.models import (
    Diagram,
    Notification,
    NotificationKind,
    ReplayPass,
    ShadowTurn,
    User,
)
from btcopilot.schema import (
    PDP,
    DatePrecision,
    Event,
    EventKind,
    ItemKind,
    PairBond,
    Person,
    from_dict,
    stated_date,
)

__all__ = [
    "Author",
    "Change",
    "Metered",
    "ModelCall",
    "Purpose",
    "CERTAINTY",
    "GONE",
    "choice",
    "ToolText",
    "ToolError",
    "Toolbox",
    "ToolName",
    "coded_in",
    "deltas_by_turn",
    "date_text",
    "diagram_of",
    "discussion_of",
    "statement",
    "cut_day",
    "render_record",
    "scribe_prompt",
    "scribe_toolbox",
    "keep_calls",
    "reply_event",
    "replies",
    "toolcall",
    "meanings",
    "Diagram",
    "Discussion",
    "DiscussionKind",
    "Statement",
    "ReplayPass",
    "ShadowTurn",
    "User",
    "coach_model",
    "scribe_model",
    "coding_diagram",
    "commit",
    "Invalid",
    "grant_write",
    "given",
    "give",
    "given_facts",
    "subject",
    "subject_on",
    "initials",
    "pdp_of",
    "plain",
    "pdp_from",
    "record_of",
    "to_json",
    "statements_between",
    "sitting",
    "utc_iso",
    "thread",
    "heard",
    "report_schema",
    "statement_order",
]


def meanings() -> dict:
    """What each tool argument means to the model, in the wording the private
    prompts give it (R-0305)."""
    return prompts.tool_meanings()


def coded_in(diagram_id: int, kind: ItemKind = ItemKind.Event) -> dict[int, dict]:
    """Which turn each item of one kind on a record was written from."""
    return record.coded_in(diagram_id, kind)


def deltas_by_turn(diagram_id: int, turn_ids: set[str]) -> dict[str, list[dict]]:
    """Every delta each of these turns wrote on a record, oldest first, from
    the command log, reading only those turns' changes."""
    if not turn_ids:
        return {}
    by_turn: dict[str, list[dict]] = {}
    for change in (
        Change.query.filter(
            Change.diagram_id == diagram_id, Change.turn_id.in_(turn_ids)
        )
        .order_by(Change.id)
    ):
        by_turn.setdefault(change.turn_id, []).extend(change.deltas or [])
    return by_turn


def scribe_prompt(record_text: str) -> str:
    """The scribe's system prompt, read at call time so fdserver's override is
    the one in force (R-0314)."""
    return prompts.scribe_prompt(record_text)


def scribe_toolbox(diagram_id: int, user_id: int, statement_id: int, turn_id: str):
    """The review's own hands on a coder's record: the app's commit path, with
    the turn the coder was reading stamped on every change it makes."""
    return Toolbox(
        diagram_id,
        turn_id,
        user_id=user_id,
        author=Author.Review,
        statement_id=statement_id,
        repoint=True,
    )


def keep_calls(
    turn_id: str, discussion_id: int, diagram_id: int, kept: list[dict]
) -> None:
    """A scribe turn's tool calls, kept as turn_events rows the way a coach
    turn keeps its own, and its refused calls written down as the coach's are,
    so the learning loop counts them the same (R-0871)."""
    turnstore.save(turn_id, discussion_id, kept)
    db.session.flush()
    observer.refusals(diagram_id, turn_id)
    db.session.commit()


def reply_event(text: str) -> dict:
    """What the scribe said back to the coder, kept as the coach's own words
    are (R-0942)."""
    return {"type": TurnEventKind.Text.value, "text": text}


def replies(turn_ids: set[str]) -> dict[str, str]:
    """What the scribe said back on each of these turns, where it said
    anything."""
    return {
        turn_id: event["text"]
        for turn_id, events in turnstore.kept(turn_ids).items()
        for event in events
        if event["type"] == TurnEventKind.Text.value
    }


def discussion_of(discussion_id: int) -> Discussion:
    return db.session.get(Discussion, discussion_id)


def statement(statement_id: int) -> Statement:
    return db.session.get(Statement, statement_id)


def cut_day(statement_id: int):
    """The day a line is named by: the day its sitting happened, or the day the
    line was written down when the sitting carries no date."""
    line = statement(statement_id)
    if line is None:
        return None
    return line.discussion.discussion_date or line.created_at


def initials(user: User | None) -> str:
    """One coder reads as one kind of name everywhere: initials from their name,
    or, with no name, initials of the parts of their address before the @, each
    keeping any digits that tell two coders apart. A whole address is never put
    on a screen."""
    if user is None:
        return "someone"
    letters = [part[0] for part in (user.first_name, user.last_name) if part]
    if letters:
        return ".".join(letters) + "."
    parts = [
        part for part in re.split(r"[^A-Za-z0-9]+", user.username.split("@")[0]) if part
    ]
    return "".join(part[0].upper() + re.sub(r"\D", "", part) + "." for part in parts)


def given(user: User | None) -> str:
    """What an agenda line calls a coder: their first name where they have one,
    and their initials where they do not. A whole address is never put on a
    screen."""
    if user is None:
        return "someone"
    return user.first_name.strip() or initials(user)


def diagram_of(diagram_id: int) -> Diagram:
    return db.session.get(Diagram, diagram_id)


def render_record(diagram_id: int) -> str:
    """The record as the models read it, ending with its version: the scribe
    has no read tool to learn the version a change must name from (R-0480)."""
    diagram = diagram_of(diagram_id)
    text = render(diagram.get_diagram_data())
    return "\n\n".join(s for s in (text, version_line(diagram.version)) if s)


def to_json(value):
    """A plain Python value in the record's own tagged JSON form."""
    return diagramjson.to_json(value)


def plain(value):
    """One field of a record as a screen reads it: an enum as its word, a day
    as its date, everything else as it stands."""
    if isinstance(value, str) or isinstance(value, (int, float, bool)) or value is None:
        return getattr(value, "value", value)
    return date_text(value) or getattr(value, "value", value)


def record_of(diagram: Diagram) -> dict:
    return diagramjson.loads(diagram.data)


def pdp_of(diagram: Diagram) -> PDP:
    """The record as typed items, which is what the F1 matcher compares."""
    return pdp_from(record_of(diagram))


def pdp_from(data: dict) -> PDP:
    return PDP(
        people=[from_dict(Person, p) for p in data.get("people") or []],
        events=[from_dict(Event, _dated(e)) for e in data.get("events") or []],
        pair_bonds=[from_dict(PairBond, b) for b in data.get("pair_bonds") or []],
    )


def _dated(event: dict) -> dict:
    return dict(
        event,
        dateTime=date_text(event.get("dateTime")),
        endDateTime=date_text(event.get("endDateTime")),
    )


def coding_diagram(
    user, name: str, source: Diagram | None = None, scratch: bool = False
) -> Diagram:
    """A coder's own record for a case: the one they built last time carried
    forward, or a fresh empty one."""
    diagram = Diagram(
        user_id=user.id,
        name=name,
        data=diagramjson.dumps(record_of(source) if source is not None else {}),
        scratch=scratch,
    )
    db.session.add(diagram)
    db.session.flush()
    return diagram


#: What a coding copy holds of the case before anything is coded: the person
#: the case belongs to and their birth, which every user gives first (R-0940).
GIVEN_PERSON = ("name", "last_name", "gender", "primary")
GIVEN_BIRTH = ("dateTime", "dateCertainty", "datePrecision")
#: The turn the given facts are written under, so a catch-up can be taken back.
GIVEN = "given"


def subject(case: Diagram) -> tuple[dict | None, dict | None]:
    """The person a case belongs to and their dated birth, as the case's own
    diagram holds them."""
    data = case.get_diagram_data()
    person = profile.own(data)
    return person, profile.birth(data, person["id"]) if person else None


def subject_on(copy: Diagram, person: dict) -> dict | None:
    """The case's person on a coding copy: the one flagged as the person the
    copy belongs to, or else the one person holding their exact name."""
    people = copy.get_diagram_data().people
    flagged = next((p for p in people if p.get("primary")), None)
    if flagged is not None:
        return flagged
    name = (person.get("name"), person.get("last_name"))
    named = [p for p in people if (p.get("name"), p.get("last_name")) == name]
    if len(named) > 1:
        raise ValueError(f"{len(named)} people on diagram {copy.id} are named {person.get('name')}")
    return named[0] if named else None


def given_facts(case: Diagram, copy: Diagram) -> list[dict]:
    """The deltas that put the case's person and their birth on a coding copy
    lacking them; none when the copy already has the person and a birth of
    them at any precision, or the case has no person (R-0940)."""
    person, birth = subject(case)
    if person is None:
        return []
    data = copy.get_diagram_data()
    there = subject_on(copy, person)
    deltas = []
    if there is None:
        there = {"id": record.next_id(data)}
        deltas += _fields(ItemKind.Person, there["id"], person, GIVEN_PERSON)
    born = any(
        e.get("kind") == EventKind.Birth.value and e.get("child") == there["id"]
        for e in data.events
    )
    if birth is not None and not born:
        one = there["id"] + 1 if deltas else record.next_id(data)
        made = dict(birth, kind=EventKind.Birth.value, child=there["id"])
        if made.get("datePrecision") is None:
            made["datePrecision"] = _precision(birth["dateTime"]).value
        deltas += _fields(ItemKind.Event, one, made, ("kind", "child") + GIVEN_BIRTH)
    return deltas


def _precision(value) -> DatePrecision:
    """How much of a date its own form says: a Pro date is a whole day."""
    return stated_date(value if isinstance(value, str) else date_text(value))[1]


def _fields(kind: ItemKind, item_id: int, item: dict, fields: tuple) -> list[dict]:
    return [
        {"item_kind": kind.value, "item_id": item_id, "field": field, "after": to_json(item[field])}
        for field in fields
        if item.get(field) is not None
    ]


def give(case: Diagram, copy: Diagram, user_id: int) -> Change | None:
    """The case's given facts written on a coding copy as one change, which
    `diagrams undo` takes back."""
    deltas = given_facts(case, copy)
    if not deltas:
        return None
    return commit(copy.id, deltas, user_id, f"{GIVEN}:{uuid.uuid4().hex}")


def grant_write(diagram: Diagram, user):
    diagram.grant_access(user, btcopilot.ACCESS_READ_WRITE)


def commit(diagram_id: int, deltas: list[dict], user_id: int, turn_id: str) -> Change:
    """A decision written onto the case's record, logged as the review's own."""
    return record.apply(
        diagram_id,
        deltas,
        author=Author.Review,
        turn_id=turn_id,
        user_id=user_id,
    )


def thread(diagram_id: int) -> list[Statement]:
    """Every sitting's lines on one family as the chat app shows them: the
    sittings in the order they started, each one's lines in their order."""
    found = (
        Statement.query.join(Discussion)
        .filter(Discussion.diagram_id == diagram_id)
        .all()
    )
    started: dict[int, datetime.datetime] = {}
    for s in found:
        was = started.get(s.discussion_id)
        started[s.discussion_id] = (
            s.created_at if was is None else min(was, s.created_at)
        )
    return sorted(
        found,
        key=lambda s: (started[s.discussion_id], s.discussion_id, s.order or 0, s.id),
    )


def heard(lines: list[Statement]) -> list[Statement]:
    """Lines less the person's words whose turn failed with no reply and that
    they sent again word for word later on: those never became part of the
    conversation. A repeat the coach answered stays."""
    sharing = Counter(s.turn_id for s in lines if s.turn_id)
    failed = _failed(set(sharing))
    return [
        s
        for at, s in enumerate(lines)
        if not (
            s.turn_id
            and sharing[s.turn_id] == 1
            and s.turn_id in failed
            and any(
                later.speaker_id == s.speaker_id
                and (later.text or "").strip() == (s.text or "").strip()
                for later in lines[at + 1 :]
            )
        )
    ]


def _failed(turn_ids: set[str]) -> set[str]:
    """The turns whose last ending event is a failure, read from the kinds of
    their ending events alone in one query."""
    if not turn_ids:
        return set()
    last = (
        db.session.query(TurnEvent.turn_id, func.max(TurnEvent.seq).label("seq"))
        .filter(
            TurnEvent.turn_id.in_(turn_ids),
            TurnEvent.kind.in_(
                (TurnEventKind.Done.value, TurnEventKind.Failed.value)
            ),
        )
        .group_by(TurnEvent.turn_id)
        .subquery()
    )
    return {
        turn_id
        for (turn_id,) in db.session.query(TurnEvent.turn_id)
        .join(
            last,
            (TurnEvent.turn_id == last.c.turn_id) & (TurnEvent.seq == last.c.seq),
        )
        .filter(TurnEvent.kind == TurnEventKind.Failed.value)
    }


def sitting(discussion_id: int) -> list[Statement]:
    found = Statement.query.filter_by(discussion_id=discussion_id).all()
    return sorted(found, key=lambda s: (s.order or 0, s.id or 0))


def statement_order(diagram_id: int) -> dict[int, int]:
    """Each line's place in the family's thread, counted from 1."""
    return {s.id: at for at, s in enumerate(thread(diagram_id), start=1)}


def statements_between(diagram_id: int, start_id: int, end_id: int) -> list[Statement]:
    lines = thread(diagram_id)
    ids = [s.id for s in lines]
    if start_id not in ids or end_id not in ids:
        raise ValueError("a cut's first and last lines must be lines of its thread")
    return lines[ids.index(start_id) : ids.index(end_id) + 1]


def first_statement(diagram_id: int) -> Statement | None:
    return next(iter(thread(diagram_id)), None)


def last_statement(diagram_id: int) -> Statement | None:
    lines = thread(diagram_id)
    return lines[-1] if lines else None


def next_statement(diagram_id: int, after_id: int) -> Statement | None:
    lines = thread(diagram_id)
    ids = [s.id for s in lines]
    if after_id not in ids or ids.index(after_id) + 1 == len(ids):
        return None
    return lines[ids.index(after_id) + 1]


def coach_model(
    name: str | None = None, effort: str | None = COACH_EFFORT
) -> CoachModel:
    return CoachModel(model=name, effort=effort)


def scribe_model(name: str):
    """The scribe's model, picked the way the coach's is: Gemini where Gemini
    is served, and a plain failure on Bedrock, which has none (R-0885)."""
    return model_for(name)


def replay_into(
    diagram: Diagram,
    discussion: Discussion,
    statements,
    model=None,
    cap: Decimal | None = None,
    copy: Discussion | None = None,
    replies: list[dict] | None = None,
) -> tuple[Discussion, list[dict]]:
    """Run the coach over a cut's turns, writing what it codes onto `diagram`,
    as scratch turns that charge no one, in `copy` or a new scratch session.
    Each turn's tool calls are kept and watched as a real turn's are, so its
    mistakes are written down. With a cap, no paid call is made that could
    take the diagram's replay calls past it: the turn that would is taken back
    whole, so the replay can go on from it later. Each finished turn's reply is
    appended to `replies` as it lands, so a caller keeps the turns done before
    a failing one."""
    if copy is None:
        copy = scratch_session(diagram, discussion)
    said = [s.text for s in spoken(statements)]
    replies = [] if replies is None else replies
    for text in said:
        turn = CoachTurn(
            copy,
            text,
            purpose=Purpose.Replay,
            model=model,
            scratch=True,
        )
        if cap is not None:
            turn.model.afford = lambda: afford(diagram.id, cap)
        try:
            reply = turn.run()
        except OverCap:
            db.session.rollback()
            _taken_back(turn)
            break
        turnstore.save(
            turn.turn_id,
            copy.id,
            turn.kept + [turnstore.done(reply["statement_id"])],
        )
        observer.observe(diagram.id, turn.turn_id, turn.data)
        db.session.commit()
        replies.append(reply)
    return copy, replies


def afford(diagram_id: int, cap: Decimal) -> None:
    """Refuse the next replay call on the record when it could pass the cap,
    if it costs as much as the dearest so far."""
    total, dearest = (
        db.session.query(
            func.coalesce(func.sum(ModelCall.cost_usd), 0),
            func.coalesce(func.max(ModelCall.cost_usd), 0),
        )
        .filter(ModelCall.diagram_id == diagram_id, ModelCall.purpose == Purpose.Replay)
        .one()
    )
    if total >= cap or total + dearest > cap:
        raise OverCap(f"${total} of ${cap} spent; the dearest call cost ${dearest}")


def _taken_back(turn: CoachTurn) -> None:
    """A turn stopped at the cap leaves nothing but its model calls: an edit is
    committed as it is made, and the person's words with it."""
    session = turn.discussion
    if Change.query.filter_by(diagram_id=turn.diagram.id, turn_id=turn.turn_id).first():
        record.undo(
            turn.diagram.id,
            turn.turn_id,
            author=Author.Coach,
            user_id=session.user_id,
            session_id=session.id,
        )
    Statement.query.filter_by(discussion_id=session.id, turn_id=turn.turn_id).delete()
    db.session.commit()


def scratch_session(diagram: Diagram, discussion: Discussion) -> Discussion:
    copy = Discussion(
        user_id=discussion.user_id,
        diagram_id=diagram.id,
        # an untitled copy would spend a naming call on its first turn
        title=discussion.title or f"Replay of session {discussion.id}",
        title_set_by_user=True,
        discussion_date=discussion.discussion_date,
        speakers=[
            Speaker(name="Client", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(copy)
    db.session.flush()
    copy.chat_user_speaker_id = copy.speakers[0].id
    copy.chat_ai_speaker_id = copy.speakers[1].id
    db.session.commit()
    return copy


def spoken(statements) -> list[Statement]:
    """The person's words among a cut's statements, each one coach turn."""
    return [
        s
        for s in statements
        if s.text and s.speaker and s.speaker.type == SpeakerType.Subject
    ]


def spent(diagram_id: int) -> Decimal:
    return (
        db.session.query(func.coalesce(func.sum(ModelCall.cost_usd), 0))
        .filter(ModelCall.diagram_id == diagram_id, ModelCall.purpose == Purpose.Replay)
        .scalar()
    )


def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()
