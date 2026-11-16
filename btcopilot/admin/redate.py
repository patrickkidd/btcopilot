"""The one pass that re-dates every event a writer stood a date in for, by
rereading the conversation it was written from [Oracle: R-0960, R-0958,
R-0772]. `plan` makes one model call per event: a turn on the coach's default
model, with the coach's prompt and the diagram's map, the conversation up to
and including the message the event was written from, and the event tool
alone. It saves each call with what it would write and writes nothing.
`apply` makes exactly those calls through the event tool, the coach's own
path; `undo` takes them back. Back the database up before `apply`. A call is
never made again for a nicer answer: a new plan is a new plan."""

import datetime
import enum
import json
import pathlib
from types import SimpleNamespace

import click
from flask import current_app

from btcopilot import clock, profile, record
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.coachmodel import model_for
from btcopilot.coachturn import drain
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import Author, Change, Diagram, Discussion, Purpose, Statement
from btcopilot.prompts import get_agent_prompt
from btcopilot.recordtext import date_text, event_line, outline
from btcopilot.review import scribe
from btcopilot.review.models import Coding, Note
from btcopilot.schema import ItemKind, stated_date
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas

TURN = "redate:{}:{}"
PLANS = "redate-plans"
COLUMNS = ["diagram", "event", "copy", "kind", "old", "new", "certainty", "evidence", "left"]


class Kind(enum.StrEnum):
    """The three kinds of R-0958, and nothing said at all."""

    Said = "a"
    Order = "b"
    Pattern = "c"
    Nothing = "none"


class Left(enum.StrEnum):
    Unwritten = "no message it was written from"
    Uncalled = "the model made no call for it"
    Moved = "its date changed since the plan"


KIND = {
    "type": "string",
    "enum": [k.value for k in Kind],
    "description": (
        "a: a time was said somewhere in the conversation; b: no time, but the order "
        "was said or follows from the family structure; c: a standing pattern, not a "
        "point in time; none: nothing at all places it."
    ),
}

ASK = """Nobody reads your words: this is a re-reading of a conversation, not a turn in it.

Event {id} carries a stand-in date that nobody said:
{line}

{given}Below is the conversation up to and including the message event {id} was written from. Date event {id} by the three kinds, from what the conversation and the map say: call edit_event once, on event {id} only, with kind_of_date. For a or b give the date, its date_certainty, and date_evidence with the words about when, verbatim, whenever any were said. For c or none, clear date and date_evidence. Change nothing else.

THE CONVERSATION
{thread}"""


def tools() -> list[dict]:
    """The coach's event tool with the kind of date it judged beside it."""
    (tool,) = [t for t in schemas() if t["name"] == ToolName.EditEvent]
    schema = tool["input_schema"]
    return [
        dict(
            tool,
            input_schema=dict(
                schema,
                properties={**schema["properties"], "kind_of_date": KIND},
                required=["id", "version", "kind_of_date"],
            ),
        )
    ]


def made_in(diagram_id: int, event_id) -> Change | None:
    """The change row that added the event."""
    for change in Change.query.filter_by(diagram_id=diagram_id).order_by(Change.id):
        for delta in change.deltas:
            if (
                delta["item_kind"] == ItemKind.Event.value
                and str(delta["item_id"]) == str(event_id)
                and delta["field"] is None
                and delta.get("before") is None
                and delta["after"] is not None
            ):
                return change
    return None


def _line(statement: Statement) -> str:
    who = "person" if statement.speaker_id == statement.discussion.chat_user_speaker_id else "coach"
    return f"[{who} message {statement.id}] {statement.text}"


def _upto(statements, last: Statement) -> list[Statement]:
    ordered = sorted(
        (s for s in statements if s.text),
        key=lambda s: (s.discussion.created_at, s.discussion_id, s.order or 0, s.id),
    )
    end = ordered.index(last)
    return ordered[: end + 1]


def thread(diagram: Diagram, change: Change, coding: Coding | None) -> str:
    """The owner's sessions on the family up to and including the message
    the event was written from; on a coder's copy, the case's conversation up
    to the turn the coder tapped, then the coder's own words on the copy up to
    the one the event was written from."""
    last = db.session.get(Statement, change.statement_id)
    if coding is None:
        said = Statement.query.join(Discussion).filter(
            Discussion.diagram_id == diagram.id, Discussion.user_id == diagram.user_id
        )
        return "\n\n".join(_line(s) for s in _upto(said, last))
    said = Statement.query.filter_by(discussion_id=last.discussion_id)
    notes = Note.query.filter_by(coding_id=coding.id).order_by(Note.id).all()
    upto = [n.turn_id for n in notes].index(change.turn_id)
    return "\n\n".join(
        [_line(s) for s in _upto(said, last)]
        + [f"[coder's words on message {n.statement_id}] {n.text}" for n in notes[: upto + 1]]
    )


class Planned(Toolbox):
    """The event tool with every check it makes and nothing written."""

    def _apply(self, deltas, statement_id=None):
        try:
            record.preview(self.diagram_id, deltas, author=self.author, turn_id=self.turn_id)
        except record.Invalid as e:
            raise ToolError(str(e), e.plain)
        return SimpleNamespace(deltas=deltas, version=None, turn_id=self.turn_id)


def _new(args: dict) -> dict:
    date = stated_date(args["date"])[0] if args.get("date") else None
    return {
        "new": date,
        "certainty": args.get("date_certainty"),
        "evidence": args.get("date_evidence"),
    }


def planned(diagram: Diagram, event: dict, made: str) -> dict:
    """The one call for one event, and what it would write."""
    data = diagram.get_diagram_data()
    coding = Coding.query.filter_by(diagram_id=diagram.id).first()
    entry = {
        "diagram": diagram.id,
        "event": event["id"],
        "copy": coding is not None,
        "kind": None,
        "old": date_text(event.get("dateTime")),
        "old_certainty": event.get("dateCertainty"),
        "new": None,
        "certainty": None,
        "evidence": None,
        "args": None,
        "left": None,
    }
    change = made_in(diagram.id, event["id"])
    if change is None or change.statement_id is None:
        return dict(entry, left=Left.Unwritten.value)
    turn_id = TURN.format(diagram.id, made)
    meter = Metered(diagram.user_id, diagram.id, turn_id, Purpose.Backfill, model=model_for())
    speaker = None if coding else profile.person_of(diagram.user, diagram)
    system = get_agent_prompt(
        record=outline(data, diagram.version, speaker), today=clock.today().isoformat()
    )
    ask = ASK.format(
        id=event["id"],
        line=event_line(event),
        given=scribe.given(coding) if coding else "",
        thread=thread(diagram, change, coding),
    )
    turn = drain(meter.turn(system, [{"role": "user", "content": ask}], tools(), turn_id))
    call = next(
        (
            c.args
            for c in turn.calls
            if c.name == ToolName.EditEvent and str(c.args.get("id")) == str(event["id"])
        ),
        None,
    )
    if call is None:
        return dict(entry, left=Left.Uncalled.value)
    args = {k: v for k, v in call.items() if k not in ("kind_of_date", "version")}
    entry.update(kind=call.get("kind_of_date"), args=args, **_new(args))
    try:
        Planned(diagram.id, turn_id, user_id=diagram.user_id).call(
            ToolName.EditEvent, {**args, "version": diagram.version}
        )
    except ToolError as e:
        entry["left"] = f"refused: {e}"
    return entry


def loaded(path: pathlib.Path) -> dict:
    saved = json.loads(path.read_text())
    if not {"made", "events"} <= set(saved):
        raise click.ClickException(f"{path} is not a plan this command saved")
    return saved


def done_at(path: pathlib.Path) -> pathlib.Path:
    return path.with_suffix(".applied.json")


@click.group("redate")
def redate():
    """Re-date the events stored at a stand-in date (1 January 1900, year 1,
    or 1 January 1970 marked unknown) by rereading the conversation: plan,
    apply, undo [Oracle: R-0960]."""


@redate.command("plan")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--plans",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help=f"Where the plan is saved; left out, {PLANS} in the instance folder.",
)
@rows_option
def plan(diagram_id, plans):
    """One model call per event at a stand-in date, on every record but the
    scratch copies, coders' copies included; saves what each call would write,
    with the kind of date it judged, and writes nothing to any record."""
    query = Diagram.query.filter(Diagram.scratch.is_(False))
    if diagram_id:
        query = query.filter(Diagram.id == diagram_id)
    made = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    rows = [
        planned(diagram, event, made)
        for diagram in query.order_by(Diagram.id)
        for event in diagram.get_diagram_data().events
        if record.standin(event)
    ]
    folder = plans or pathlib.Path(current_app.instance_path) / PLANS
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"redate-{made}.json"
    path.write_text(json.dumps({"made": made, "events": rows}, indent=2, ensure_ascii=False))
    return [*COLUMNS, "plan"], [dict(row, plan=str(path)) for row in rows]


plan = writes(plan)


@redate.command("apply")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
@rows_option
def apply(path):
    """Make each call the plan saved through the event tool, one change row
    per call under the plan's turn for that record; an event whose date moved
    since the plan is left as it is."""
    saved = loaded(path)
    rows = []
    for entry in saved["events"]:
        if entry["args"] is None or entry["left"]:
            continue
        diagram = db.session.get(Diagram, entry["diagram"])
        event = next(
            (e for e in diagram.get_diagram_data().events if e["id"] == entry["event"]), None
        )
        if event is None or date_text(event.get("dateTime")) != entry["old"]:
            rows.append(dict(entry, left=Left.Moved.value))
            continue
        Toolbox(
            diagram.id, TURN.format(diagram.id, saved["made"]), user_id=diagram.user_id
        ).call(ToolName.EditEvent, {**entry["args"], "version": diagram.version})
        rows.append(entry)
    done_at(path).write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    return COLUMNS, rows


apply = writes(apply)


@redate.command("undo")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
@rows_option
def undo(path):
    """Take back every change the plan's apply made, one record at a time."""
    saved = loaded(path)
    rows = []
    for diagram_id in sorted({e["diagram"] for e in json.loads(done_at(path).read_text())}):
        turn_id = TURN.format(diagram_id, saved["made"])
        if not Change.query.filter_by(diagram_id=diagram_id, turn_id=turn_id).count():
            continue
        diagram = db.session.get(Diagram, diagram_id)
        change = record.undo(diagram_id, turn_id, author=Author.Coach, user_id=diagram.user_id)
        rows.append({"diagram": diagram_id, "change": change.id})
    return ["diagram", "change"], rows


undo = writes(undo)
