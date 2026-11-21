"""The one pass that re-dates every event a writer stood a date in for, by
rereading the conversation it was written from [Oracle: R-0960, R-0958,
R-0772]. `plan` makes one model call per event: a turn on the coach's default
model, with the coach's prompt and the diagram's map, the conversation up to
and including the message the event was written from, and the event tool
alone. It saves each call with what it would write and writes nothing.
`apply` makes exactly those calls through the event tool, the coach's own
path; `undo` takes them back. Back the database up before `apply`. A call is
never made again for a nicer answer: a new plan is a new plan. An event with
no message it was written from has nothing to reread: nothing was said about
when, so it is planned with its date cleared and no call. A plan that would
leave a stand-in, given again by the model or left by it, clears the date
instead, so no event it covers ends at a stand-in (R-0956). On a coder's copy
it also rereads the dates the scribe judged itself, now with the birth dates:
one dated before the birth of its person, and one the scribe estimated with no
words about when; the second is written only when the words give a time, and
a year said anywhere in the thread is the speaker's, never selected (R-0979)."""

import datetime
import enum
import json
import pathlib
import re
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
from btcopilot.schema import DateCertainty, EventKind, ItemKind, stated_date
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas

TURN = "redate:{}:{}"
PLANS = "redate-plans"
APPLIED = ".applied.json"
FAILED = "failed: "
REFUSED = "refused when applied: "
CLEARED = ["date", "date_evidence"]
COLUMNS = [
    "diagram", "event", "title", "copy", "why", "message", "kind", "old", "new", "certainty", "evidence", "cleared", "left"
]
BORN_ON = (EventKind.Birth.value, EventKind.Adopted.value)


class Kind(enum.StrEnum):
    """The three kinds of R-0958, and nothing said at all."""

    Said = "a"
    Order = "b"
    Pattern = "c"
    Nothing = "none"


class Why(enum.StrEnum):
    """Why the plan holds an event [Oracle: R-0960, R-0979]."""

    Standin = "a stand-in date"
    Unborn = "dated before the birth of its person"
    Guess = "the scribe's own estimate"


class Left(enum.StrEnum):
    Failed = "failed when planned"
    Moved = "its date changed since the plan"
    Unchanged = "the reread gives no better date"


class Cleared(enum.StrEnum):
    """Why a plan clears a date the model did not clear."""

    Refused = "cleared after a refused estimate"
    Kept = "cleared: the model left the stand-in"


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

{given}Below is the conversation up to and including the message event {id} was written from. Date event {id} by the three kinds, from what the conversation and the map say: call edit_event once, on event {id} only, with kind_of_date. For a or b give the date, its date_certainty, and date_evidence with the words about when, verbatim, whenever any were said. For c or none, clear {cleared}. Change nothing else.

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


def history(diagram_id: int) -> tuple[dict[str, Change], dict[str, Change]]:
    """Per event id, the change row that added it and the last that set its date."""
    added, dated = {}, {}
    for change in Change.query.filter_by(diagram_id=diagram_id).order_by(Change.id):
        for delta in change.deltas:
            if delta["item_kind"] != ItemKind.Event.value:
                continue
            key = str(delta["item_id"])
            made = delta["field"] is None and delta.get("before") is None and delta["after"] is not None
            if made:
                added.setdefault(key, change)
            if made or delta["field"] == "dateTime":
                dated[key] = change
    return added, dated


def made_in(diagram_id: int, event_id) -> Change | None:
    """The change row that added the event."""
    return history(diagram_id)[0].get(str(event_id))


def origin(diagram: Diagram, change: Change) -> tuple[Statement, Cut | None, Coding | None]:
    """The message the event was written from and, on a coder's copy, its cut
    and coding."""
    last = db.session.get(Statement, change.statement_id)
    if last.discussion.diagram_id == diagram.id:
        return last, None, None
    coding = Coding.query.filter_by(diagram_id=diagram.id).first()
    return last, coding.cut if coding else cut_of(last), coding


def born(copy: Diagram, cut: Cut, event: dict) -> str | None:
    """The day the event's person was born: from the copy, else, for the
    case's person, from the case, as the scribe is given it [Oracle: R-0979]."""
    if event.get("kind") in BORN_ON or event.get("person") is None:
        return None
    birth = profile.birth(copy.get_diagram_data(), event["person"])
    if birth is None:
        person, birth = adapter.subject(adapter.diagram_of(cut.diagram_id))
        if person is None or (adapter.subject_on(copy, person) or {}).get("id") != event["person"]:
            return None
    return record.day(birth.get("dateTime")) if birth else None


def chosen(diagram: Diagram, event: dict, writes: tuple | None) -> Why | None:
    """Why the catch-up rereads the event, if it does: a stand-in date on any
    record; on a coder's copy, a date the scribe set itself that no one said,
    before the birth of the event's person or estimated with no words about
    when [Oracle: R-0960, R-0979]."""
    if record.standin(event):
        return Why.Standin
    on = record.day(event.get("dateTime"))
    if on is None or writes is None:
        return None
    added, dated = writes
    change = added.get(str(event["id"]))
    setter = dated.get(str(event["id"]))
    if change is None or change.statement_id is None or setter is None or setter.author != Author.Review:
        return None
    _, cut, coding = origin(diagram, change)
    if cut is None or on[:4] in re.sub(r"\[[^\]]*\]", "", thread(change, cut, coding)):
        return None
    birth = born(diagram, cut, event)
    if birth and on < birth:
        return Why.Unborn
    unknown = event.get("dateCertainty") == DateCertainty.Unknown
    return Why.Guess if unknown and not event.get("dateEvidence") else None


def scribed(diagram_id: int) -> tuple | None:
    """The event history of a record the scribe wrote, a coder's copy; None
    for any other record."""
    if not Change.query.filter_by(diagram_id=diagram_id, author=Author.Review).first():
        return None
    return history(diagram_id)


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
        "title": event.get("title") or event.get("description"),
        "copy": None,
        "why": None,
        "message": None,
        "kind": None,
        "old": date_text(event.get("dateTime")),
        "old_certainty": event.get("dateCertainty"),
        "new": None,
        "certainty": None,
        "evidence": None,
        "args": None,
        "cleared": None,
        "left": None,
    }


def planned(diagram: Diagram, event: dict, made: str, why: Why = Why.Standin) -> dict:
    """The one call for one event, and what it would write."""
    data = diagram.get_diagram_data()
    coding = Coding.query.filter_by(diagram_id=diagram.id).first()
    entry = dict(blank(diagram, event), copy=coding is not None, why=why.value)
    turn_id = TURN.format(diagram.id, made)
    change = made_in(diagram.id, event["id"])
    if change is None or change.statement_id is None:
        return checked(diagram, event, turn_id, entry, Kind.Nothing, {"id": event["id"], "clear": CLEARED})
    last, cut, coding = origin(diagram, change)
    copy = cut is not None
    entry.update(copy=copy, message=last.id)
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
        cleared=" and ".join(CLEARED),
    )
    turn = drain(meter.turn(system, [{"role": "user", "content": ask}], tools(), turn_id))
    call = next(
        (
            c.args
            for c in turn.calls
            if c.name == ToolName.EditEvent and str(c.args.get("id")) == str(event["id"])
        ),
        {"id": event["id"]},
    )
    args = {k: v for k, v in call.items() if k not in ("kind_of_date", "version")}
    if not better(why, call.get("kind_of_date"), args):
        return dict(entry, kind=call.get("kind_of_date"), left=Left.Unchanged.value)
    return checked(diagram, event, turn_id, entry, call.get("kind_of_date"), args)


def better(why: Why, kind, args: dict) -> bool:
    """Whether the reread changes a date the scribe judged: one before the
    birth by any of the three kinds, an estimate only by a time said in words
    [Oracle: R-0979]."""
    if why is Why.Standin:
        return True
    if why is Why.Unborn:
        return bool(args.get("date") or args.get("clear"))
    return kind == Kind.Said and bool(args.get("date") and args.get("date_evidence"))


def kept(event: dict, args: dict) -> Cleared | None:
    """Why the write would leave the event at a stand-in date, if it would."""
    if "date" in args.get("clear", []):
        return None
    after = {
        "dateTime": _new(args)["new"] or event.get("dateTime"),
        "dateCertainty": args.get("date_certainty") or event.get("dateCertainty"),
    }
    if not record.standin(after):
        return None
    return Cleared.Refused if args.get("date") else Cleared.Kept


def checked(diagram: Diagram, event: dict, turn_id: str, entry: dict, kind, args: dict) -> dict:
    """The entry with the write it plans, failed when the event tool refuses
    it; a write that would leave a stand-in clears the date instead."""
    why = kept(event, args)
    if why:
        args = {"id": event["id"], "clear": CLEARED}
    entry = dict(entry, kind=kind, args=args, cleared=why and why.value, **_new(args))
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
    or 1 January 1970 marked unknown), and on coders' copies the dates the
    scribe judged itself, by rereading the conversation: plan, apply, undo
    [Oracle: R-0960, R-0979]."""


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
        made = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%f")
        path = folder / f"redate-{made}.json"
        saved = {"made": made, "events": []}
    else:
        saved = loaded(path)
    held = {(e["diagram"], str(e["event"])): e for e in saved["events"]}
    for diagram in query.order_by(Diagram.id):
        writes = scribed(diagram.id)
        for event in diagram.get_diagram_data().events:
            key = (diagram.id, str(event["id"]))
            if key in held and not failed(held[key]):
                continue
            why = chosen(diagram, event, writes)
            if why is None:
                continue
            held[key] = attempted(diagram, event, saved["made"], why)
            saved["events"] = list(held.values())
            path.write_text(json.dumps(saved, indent=2, ensure_ascii=False))
    rows = saved["events"]
    kinds = Counter(r["kind"] for r in rows if r["kind"] and not failed(r))
    click.echo(
        f"{len(rows)} events in {path}: "
        + ", ".join(f"kind {k} {kinds[k.value]}" for k in Kind)
        + f"; no message to reread {sum(r['args'] is not None and not r.get('message') for r in rows)}"
        + "".join(f"; {why.value} {sum(r.get('cleared') == why for r in rows)}" for why in Cleared)
        + f"; {Left.Unchanged.value} {sum(r['left'] == Left.Unchanged for r in rows)}"
        + f"; failed {sum(failed(r) for r in rows)}",
        err=True,
    )
    return [*COLUMNS, "plan"], [dict(row, plan=str(path)) for row in rows]


def failed(entry: dict) -> bool:
    return (entry["left"] or "").startswith(FAILED)


def unapplied(folder: pathlib.Path) -> pathlib.Path | None:
    """The newest plan in the folder, when apply has not run it: an older plan
    a newer one replaced is never continued."""
    plans = [p for p in sorted(folder.glob("redate-*.json")) if not p.name.endswith(APPLIED)]
    return plans[-1] if plans and not done_at(plans[-1]).exists() else None


def attempted(diagram: Diagram, event: dict, made: str, why: Why) -> dict:
    """The planned call, or the event with the error its call failed on: one
    event's failure never loses the rest of the plan."""
    try:
        return planned(diagram, event, made, why)
    except Exception as e:  # the plan's error boundary: kept per event, never retried
        db.session.rollback()
        traceback.print_exc()
        return dict(blank(diagram, event), why=why.value, left=f"{FAILED}{type(e).__name__}: {e}")


plan = writes(plan)


@redate.command("apply")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path))
@rows_option
def apply(path):
    """Make each call the plan saved through the event tool, one change row
    per call under the plan's turn for that record; an event whose date moved
    since the plan is left as it is, and one the event tool now refuses is
    counted as refused. Runs once per plan. Ends with what it did, saved into
    the plan too."""
    saved = loaded(path)
    if done_at(path).exists():
        raise click.ClickException(f"{path} was applied already; undo it or plan again")
    rows = [applied(entry, saved["made"]) for entry in saved["events"]]
    done_at(path).write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    written = [r for r in rows if not r["left"]]
    owners = {db.session.get(Diagram, r["diagram"]).user_id for r in written}
    saved["applied"] = {
        "written": len(written),
        "left": dict(Counter(r["left"] for r in rows if r["left"] and not refused(r))),
        "refused": sum(refused(r) for r in rows),
        "cleared": dict(Counter(r["cleared"] for r in written if r.get("cleared"))),
        "diagrams": len({r["diagram"] for r in written}),
        "users": len(owners),
    }
    path.write_text(json.dumps(saved, indent=2, ensure_ascii=False))
    line = summary(saved["applied"])
    click.get_current_context().call_on_close(lambda: click.echo(line, err=True))
    return COLUMNS, rows


def applied(entry: dict, made: str) -> dict:
    """One planned write made, or the reason it was left."""
    if failed(entry):
        return dict(entry, left=Left.Failed.value)
    if entry["left"]:
        return entry
    diagram = db.session.get(Diagram, entry["diagram"])
    event = next(
        (e for e in diagram.get_diagram_data().events if e["id"] == entry["event"]), None
    )
    if event is None or date_text(event.get("dateTime")) != entry["old"]:
        return dict(entry, left=Left.Moved.value)
    try:
        Toolbox(diagram.id, TURN.format(diagram.id, made), user_id=diagram.user_id).call(
            ToolName.EditEvent, {**entry["args"], "version": diagram.version}
        )
    except ToolError as e:
        return dict(entry, left=f"{REFUSED}{e}")
    return entry


def refused(entry: dict) -> bool:
    return (entry["left"] or "").startswith(REFUSED)


def summary(done: dict) -> str:
    left = ", ".join(f"{n} {why}" for why, n in sorted(done["left"].items())) or "none"
    return (
        f"{done['written']} events written"
        + "".join(f", {done['cleared'].get(why.value, 0)} {why.value}" for why in Cleared)
        + f"; {sum(done['left'].values())} left as they were"
        f" ({left}); {done['refused']} refused; {done['diagrams']} diagrams;"
        f" {done['users']} users"
    )


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
