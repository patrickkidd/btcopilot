"""The one door between the review and the two apps it reads.

Nothing else under btcopilot/review may import btcopilot.personal or
btcopilot.pro; the import test in the review tests enforces it. Keeping the
whole surface in one file means the review can be read, moved or replaced
without hunting for the places it reached into the apps.
"""

import datetime
import re

import btcopilot
from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.personal import record
from btcopilot.personal.record import Invalid
from btcopilot.personal.coachmodel import CoachModel
from btcopilot.personal.coachturn import CoachTurn
from btcopilot.personal.models import (
    Author,
    Change,
    Discussion,
    DiscussionKind,
    Speaker,
    SpeakerType,
    Statement,
)
from btcopilot.personal.recordtext import date_text, render
from btcopilot.personal.toolbox import EDITS, ToolError, Toolbox, schemas
from btcopilot.pro.models import Diagram, User
from btcopilot.schema import PDP, Event, PairBond, Person, from_dict

__all__ = [
    "Author",
    "Change",
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
    "scribe_toolbox",
    "write_tools",
    "Diagram",
    "Discussion",
    "DiscussionKind",
    "Statement",
    "User",
    "case_diagram",
    "coach_model",
    "coding_diagram",
    "commit",
    "Invalid",
    "grant_write",
    "initials",
    "pdp_of",
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


def coded_in(diagram_id: int) -> dict[int, dict]:
    """Which turn each event on a record was written from."""
    return record.coded_in(diagram_id)


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


def coding_diagram(user, name: str, source: Diagram | None = None) -> Diagram:
    """A coder's own record for a case: the one they built last time carried
    forward, or a fresh empty one."""
    diagram = Diagram(
        user_id=user.id,
        name=name,
        data=diagramjson.dumps(record_of(source) if source is not None else {}),
    )
    db.session.add(diagram)
    db.session.flush()
    return diagram


def grant_write(diagram: Diagram, user):
    diagram.grant_access(user, btcopilot.ACCESS_READ_WRITE)


def commit(diagram_id: int, deltas: list[dict], user_id: int, turn_id: str) -> Change:
    """A settle written onto the case's record, logged as the review's own."""
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


def coach_model(name: str | None = None) -> CoachModel:
    return CoachModel(model=name)


def replay_into(diagram: Diagram, discussion: Discussion, statements, model=None):
    """Run the coach over a cut's turns, writing what it codes onto `diagram`.

    The replay harness owns the loop; this only points it at the review's own
    diagram and hands back what the coach was."""
    copy = Discussion(
        user_id=discussion.user_id,
        diagram_id=diagram.id,
        title=discussion.title,
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

    said = [
        s.text
        for s in statements
        if s.text and s.speaker and s.speaker.type == SpeakerType.Subject
    ]
    turn_id = f"review-replay-{discussion.id}"
    for text in said:
        CoachTurn(copy, text, model=model, session_id=turn_id).run()
    return copy


def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()
