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
import traceback
from collections import Counter
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
from btcopilot.review import adapter, scribe
from btcopilot.review.models import Coding, Cut, Note
from btcopilot.schema import ItemKind, stated_date
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas

TURN = "redate:{}:{}"
PLANS = "redate-plans"
APPLIED = ".applied.json"
FAILED = "failed: "
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
    ordered = [s for s in statements if s.text]
    return ordered[: ordered.index(last) + 1]


def cut_of(last: Statement) -> Cut:
    """The cut on the case whose lines hold the message: a coder's copy keeps
    it when its coding row was reset."""
    case = last.discussion.diagram_id
    (cut,) = [
        c
        for c in Cut.query.filter_by(diagram_id=case)
        if last in adapter.statements_between(case, c.start_statement_id, c.end_statement_id)
    ]
    return cut


def thread(change: Change, cut: Cut | None, coding: Coding | None) -> str:
    """The writer's sessions on the family up to and including the message
    the event was written from; on a coder's copy, the cut's lines up to that
    message, then the coder's own words on the copy up to the one the event
    was written from, when the copy still has its coding."""
    last = db.session.get(Statement, change.statement_id)
    if cut is None:
        said = Statement.query.join(Discussion).filter(
            Discussion.diagram_id == last.discussion.diagram_id,
            Discussion.user_id == last.discussion.user_id,
        )
        ordered = sorted(
            said, key=lambda s: (s.discussion.created_at, s.discussion_id, s.order or 0, s.id)
        )
        return "\n\n".join(_line(s) for s in _upto(ordered, last))
    lines = _upto(
        adapter.statements_between(cut.diagram_id, cut.start_statement_id, cut.end_statement_id),
        last,
    )
    notes = Note.query.filter_by(coding_id=coding.id).order_by(Note.id).all() if coding else []
    upto = [n.turn_id for n in notes].index(change.turn_id) + 1 if notes else 0
    return "\n\n".join(
        [_line(s) for s in lines]
        + [f"[coder's words on message {n.statement_id}] {n.text}" for n in notes[:upto]]
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


def blank(diagram: Diagram, event: dict) -> dict:
    return {
        "diagram": diagram.id,
        "event": event["id"],
        "copy": None,
        "kind": None,
        "old": date_text(event.get("dateTime")),
        "old_certainty": event.get("dateCertainty"),
        "new": None,
        "certainty": None,
        "evidence": None,
        "args": None,
        "left": None,
    }


def planned(diagram: Diagram, event: dict, made: str) -> dict:
    """The one call for one event, and what it would write."""
    data = diagram.get_diagram_data()
    coding = Coding.query.filter_by(diagram_id=diagram.id).first()
    entry = dict(blank(diagram, event), copy=coding is not None)
    change = made_in(diagram.id, event["id"])
    if change is None or change.statement_id is None:
        return dict(entry, left=Left.Unwritten.value)
    last = db.session.get(Statement, change.statement_id)
    copy = last.discussion.diagram_id != diagram.id
    cut = (coding.cut if coding else cut_of(last)) if copy else None
    entry["copy"] = copy
    turn_id = TURN.format(diagram.id, made)
    meter = Metered(diagram.user_id, diagram.id, turn_id, Purpose.Backfill, model=model_for())
    speaker = None if copy else profile.person_of(diagram.user, diagram)
    system = get_agent_prompt(
        record=outline(data, diagram.version, speaker), today=clock.today().isoformat()
    )
    ask = ASK.format(
        id=event["id"],
        line=event_line(event),
        given=scribe.given(cut.diagram_id) if cut else "",
        thread=thread(change, cut, coding),
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
        entry["left"] = f"{FAILED}{e}"
    return entry


def loaded(path: pathlib.Path) -> dict:
    saved = json.loads(path.read_text())
    if not {"made", "events"} <= set(saved):
        raise click.ClickException(f"{path} is not a plan this command saved")
    return saved


def done_at(path: pathlib.Path) -> pathlib.Path:
    return path.with_suffix(APPLIED)


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
@click.option("--new", "fresh", is_flag=True, help="Start a new plan, not the unapplied one.")
@rows_option
def plan(diagram_id, plans, fresh):
    """One model call per event at a stand-in date, on every record but the
    scratch copies, coders' copies included; saves what each call would write,
    with the kind of date it judged, and writes nothing to any record. The plan
    is saved after every event. An event whose call fails, or whose write the
    event tool refuses, is kept in the plan as failed with its error and is
    never applied. A rerun continues the newest plan not yet applied and calls
    the model again only for its failed events and the events it does not hold;
    an event planned without a failure is never called again."""
    query = Diagram.query.filter(Diagram.scratch.is_(False))
    if diagram_id:
        query = query.filter(Diagram.id == diagram_id)
    folder = plans or pathlib.Path(current_app.instance_path) / PLANS
    folder.mkdir(parents=True, exist_ok=True)
    path = None if fresh else unapplied(folder)
    if path is None:
        made = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
        path = folder / f"redate-{made}.json"
        saved = {"made": made, "events": []}
    else:
        saved = loaded(path)
    held = {(e["diagram"], str(e["event"])): e for e in saved["events"]}
    for diagram in query.order_by(Diagram.id):
        for event in diagram.get_diagram_data().events:
            key = (diagram.id, str(event["id"]))
            if not record.standin(event) or (key in held and not failed(held[key])):
                continue
            held[key] = attempted(diagram, event, saved["made"])
            saved["events"] = list(held.values())
            path.write_text(json.dumps(saved, indent=2, ensure_ascii=False))
    rows = saved["events"]
    kinds = Counter(r["kind"] for r in rows if r["kind"] and not failed(r))
    click.echo(
        f"{len(rows)} events in {path}: "
        + ", ".join(f"kind {k} {kinds[k.value]}" for k in Kind)
        + f"; failed {sum(failed(r) for r in rows)}"
        + f"; not called {sum(r['left'] in {l.value for l in Left} for r in rows)}",
        err=True,
    )
    return [*COLUMNS, "plan"], [dict(row, plan=str(path)) for row in rows]


def failed(entry: dict) -> bool:
    return (entry["left"] or "").startswith(FAILED)


def unapplied(folder: pathlib.Path) -> pathlib.Path | None:
    """The newest plan in the folder that apply has not run."""
    plans = [
        p
        for p in sorted(folder.glob("redate-*.json"))
        if not p.name.endswith(APPLIED) and not done_at(p).exists()
    ]
    return plans[-1] if plans else None


def attempted(diagram: Diagram, event: dict, made: str) -> dict:
    """The planned call, or the event with the error its call failed on: one
    event's failure never loses the rest of the plan."""
    try:
        return planned(diagram, event, made)
    except Exception as e:  # the plan's error boundary: kept per event, never retried
        db.session.rollback()
        traceback.print_exc()
        return dict(blank(diagram, event), left=f"{FAILED}{type(e).__name__}: {e}")


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
