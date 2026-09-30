"""The one door between the review and the chat app it reads.

Nothing else under btcopilot/review may import the app modules; the import
test in the review tests enforces it. Keeping the whole surface in one file
means the review can be read, moved or replaced without hunting for the places
it reached into the app.
"""

import datetime
import re
from decimal import Decimal

from sqlalchemy import func

import btcopilot
from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot import observer, proactive, prompts, push, record, turnstore
from btcopilot.record import Invalid
from btcopilot.coachmodel import COACH_EFFORT, CoachModel
from btcopilot.coachturn import CoachTurn
from btcopilot.metered import Metered
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
)
from btcopilot.recordtext import date_text, render
from btcopilot.toolbox import EDITS, ToolError, Toolbox, schemas
from btcopilot.models import Diagram, Notification, NotificationKind, ShadowTurn, User
from btcopilot.schema import PDP, Event, ItemKind, PairBond, Person, from_dict

__all__ = [
    "Author",
    "Change",
    "Metered",
    "ModelCall",
    "Purpose",
    "schemas",
    "ToolError",
    "Toolbox",
    "coded_in",
    "date_text",
    "diagram_of",
    "discussion_of",
    "statement",
    "cut_day",
    "render_record",
    "scribe_prompt",
    "scribe_toolbox",
    "write_tools",
    "Diagram",
    "Discussion",
    "DiscussionKind",
    "Statement",
    "ShadowTurn",
    "User",
    "case_diagram",
    "coach_model",
    "coding_diagram",
    "commit",
    "Invalid",
    "grant_write",
    "given",
    "initials",
    "pdp_of",
    "plain",
    "pdp_from",
    "record_of",
    "to_json",
    "statements_between",
    "statement_order",
]


def write_tools() -> list[dict]:
    """Only the tools that write the record. The scribe has no reply to make
    and nothing to show, so reading and showing are not on its table."""
    names = {tool.value for tool in EDITS}
    return [schema for schema in schemas() if schema["name"] in names]


def coded_in(diagram_id: int, kind: ItemKind = ItemKind.Event) -> dict[int, dict]:
    """Which turn each item of one kind on a record was written from."""
    return record.coded_in(diagram_id, kind)


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
    )


def discussion_of(discussion_id: int) -> Discussion:
    return db.session.get(Discussion, discussion_id)


def statement(statement_id: int) -> Statement:
    return db.session.get(Statement, statement_id)


def cut_day(discussion_id: int, statement_id: int):
    """The day a cut is named by: the day the conversation happened, or the day
    the turn it ends on was written down when the session carries no date."""
    discussion = discussion_of(discussion_id)
    if discussion is not None and discussion.discussion_date:
        return discussion.discussion_date
    end = statement(statement_id)
    return end.created_at if end else None


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
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", user.username.split("@")[0]) if part]
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
    """The record as the models read it."""
    return render(diagram_of(diagram_id).get_diagram_data())


def case_diagram(discussion: Discussion) -> Diagram:
    return discussion.diagram


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


def statements_between(
    discussion_id: int, start_id: int, end_id: int
) -> list[Statement]:
    orders = statement_order(discussion_id)
    lo, hi = orders.get(start_id), orders.get(end_id)
    if lo is None or hi is None:
        raise ValueError("a cut's start and end must be statements of its session")
    return [
        s
        for s in _ordered(discussion_id)
        if lo <= (s.order or 0) <= hi  # noqa: E501
    ]


def _ordered(discussion_id: int) -> list[Statement]:
    found = Statement.query.filter_by(discussion_id=discussion_id).all()
    return sorted(found, key=lambda s: (s.order or 0, s.id or 0))


def statement_order(discussion_id: int) -> dict[int, int]:
    return {s.id: (s.order or 0) for s in _ordered(discussion_id)}


def first_statement(discussion_id: int) -> Statement | None:
    found = _ordered(discussion_id)
    return found[0] if found else None


def last_statement(discussion_id: int) -> Statement | None:
    found = _ordered(discussion_id)
    return found[-1] if found else None


def next_statement(discussion_id: int, after_id: int) -> Statement | None:
    orders = statement_order(discussion_id)
    after = orders.get(after_id)
    if after is None:
        return None
    for statement in _ordered(discussion_id):
        if (statement.order or 0) > after:
            return statement
    return None


def coach_model(
    name: str | None = None, effort: str | None = COACH_EFFORT
) -> CoachModel:
    return CoachModel(model=name, effort=effort)


def replay_into(
    diagram: Diagram,
    discussion: Discussion,
    statements,
    model=None,
    cap: Decimal | None = None,
) -> tuple[Discussion, list[dict]]:
    """Run the coach over a cut's turns, writing what it codes onto `diagram`,
    as scratch turns that charge no one. Each turn's tool calls are kept and
    watched as a real turn's are, so its mistakes are written down. With a
    cap, no turn starts once the diagram's calls cost that much."""
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

    said = [s.text for s in spoken(statements)]
    replies = []
    for text in said:
        if cap is not None and spent(diagram.id) >= cap:
            break
        turn = CoachTurn(
            copy,
            text,
            purpose=Purpose.Replay,
            model=model,
            scratch=True,
        )
        reply = turn.run()
        turnstore.save(
            turn.turn_id,
            copy.id,
            turn.kept + [turnstore.done(reply["statement_id"])],
        )
        observer.observe(diagram.id, turn.turn_id, turn.data)
        db.session.commit()
        replies.append(reply)
    return copy, replies


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
