"""The one pass that puts every diagram on FD-381's grouping rules and marks
each case report the coach wrote in the old shape out of date, so its owner's
next tap rewrites it, without waiting for the person's next turn [Oracle:
R-0772, R-0850]. `plan` decides and saves what the pass will do, with no model
call; `apply` does exactly that plan, each regroup through the same
`clusters.sync` a coach turn runs, each diagram's writes as change rows;
`undo` takes those rows back. The catch-up never calls the paid refresh of a
case report itself, and never edits a diagram by hand."""

import datetime
import enum
import json
import pathlib

import click
from flask import current_app

# btcopilot.casereport imports btcopilot.admin for its settings, and that
# package imports this module: casereport's names are read at call time.
from btcopilot import casereport, clusters, diagramjson, record
from btcopilot.admin.diagrams import find, said
from btcopilot.admin.guard import writes
from btcopilot.admin.output import emit, rows_option
from btcopilot.extensions import db
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    ModelCall,
    Observation,
    ObservationKind,
    Purpose,
)
from btcopilot.schema import CaseReportCard, ClusterSource, DiagramData
from btcopilot.toolbox import CARDS

TURN = "fd381-catchup:{}:{}"
PLANS = "fd381-catchup-plans"
CARD = record.CARD
SYNC = "clusters.sync(force=True)"


class Regroup(enum.StrEnum):
    Called = (
        "the grouping cache key differs from the stored one: one grouping call, a "
        "second when the first answer is refused"
    )
    Uncalled = (
        "the grouping cache key differs from the stored one and nothing is left to "
        "group: the app's clusters are set aside with no call"
    )
    Current = "the grouping cache key is the stored one"
    Empty = "nothing to group and no cluster of the app's drawn"


class Mark(enum.StrEnum):
    Before = "the coach last wrote the report before the deploy"
    Retired = "an entry is on the choice card, which the coach no longer writes"
    After = "the coach wrote the report after the deploy"
    # the page can show no mark on a report it cannot place in the change log
    Unlogged = "the change log holds no write of the report's cards"
    Unwritten = "the coach never wrote a report"


def marked(diagram_id: int, made: str) -> str:
    """The turn id of the change row that marks a record's report out of date
    under one plan, read at call time like the rest of casereport."""
    return f"{casereport.OUT_OF_DATE}{diagram_id}:{made}"


def regrouping(diagram: Diagram, data: DiagramData) -> Regroup:
    """Whether `sync` would group this diagram anew, and with a call: it
    calls the model only when the rules find a run or the person named when
    the most was going on (`clusters.detect_clusters`)."""
    if not clusters.behind(diagram.id, data):
        return Regroup.Current
    if clusters.candidates(data) or clusters.told_ids(diagram.id, data):
        return Regroup.Called
    if any(c.get("source") == ClusterSource.Model for c in data.drawn_clusters()):
        return Regroup.Uncalled
    return Regroup.Empty


def last_written(diagram_id: int, data: DiagramData) -> Change | None:
    """The newest change row that put an entry on a card the page shows, read
    the way `casereport.stale` reads the log: a row taken back, and the undo
    itself, count for nothing."""
    shown = {q[CARD] for q in data.questions if q.get(CARD)} & set(CARDS)
    taken = record.undone(diagram_id)
    last = None
    for change in Change.query.filter_by(diagram_id=diagram_id).order_by(Change.id):
        if change.id in taken or change.turn_id.startswith("undo:"):
            continue
        if shown.intersection(map(casereport._carded, change.deltas)):
            last = change
    return last


def marking(diagram: Diagram, data: DiagramData, since: datetime.datetime) -> Mark:
    """Whether the report is in the shape the coach wrote before the deploy:
    written before it, or holding an entry on a card the coach no longer
    writes. A report with no card the page shows was never written."""
    if not {q[CARD] for q in data.questions if q.get(CARD)} & set(CARDS):
        return Mark.Unwritten
    last = last_written(diagram.id, data)
    if last is None:
        return Mark.Unlogged
    if last.created_at < since:
        return Mark.Before
    if any(q.get(CARD) == CaseReportCard.Choice for q in data.questions):
        return Mark.Retired
    return Mark.After


def per_call() -> ModelCall | None:
    """The ledger's last measured grouping call."""
    return (
        ModelCall.query.filter_by(purpose=Purpose.Cluster)
        .order_by(ModelCall.id.desc())
        .first()
    )


def utc(value: str | None) -> datetime.datetime | None:
    """A time as git or a person writes it, as the naive UTC the change log
    keeps."""
    if value is None:
        return None
    try:
        when = datetime.datetime.fromisoformat(value)
    except ValueError:
        raise click.BadParameter(f"{value} is not a date and time") from None
    if when.tzinfo is not None:
        when = when.astimezone(datetime.UTC).replace(tzinfo=None)
    return when


def planned(diagram: Diagram, since: datetime.datetime, cost: float | None) -> dict:
    data = diagram.get_diagram_data()
    regroup, mark = regrouping(diagram, data), marking(diagram, data, since)
    return {
        "diagram": diagram.id,
        "owner": diagram.user.username if diagram.user else None,
        "regroup": regroup in (Regroup.Called, Regroup.Uncalled),
        "regroup_why": regroup.value,
        "mark": mark in (Mark.Before, Mark.Retired),
        "mark_why": mark.value,
        "estimate_usd": (
            None if cost is None else cost if regroup is Regroup.Called else 0.0
        ),
    }


def said_to(as_json: bool, *lines: str) -> None:
    """Lines after the table: under it, or apart from the JSON so it still
    parses."""
    for line in lines:
        click.echo(line, err=as_json)


@click.command("plan")
@click.option(
    "--deployed",
    required=True,
    callback=lambda ctx, param, value: utc(value),
    help="When the deploy carrying FD-381 went out, as git prints a date "
    "(2026-10-15T14:02:00+00:00) or in UTC: a report the coach last wrote before "
    "it is marked.",
)
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--plans",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    help=f"Where the plan is saved; left out, {PLANS} in the instance folder.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON, not a table.")
def plan(deployed, diagram_id, plans, as_json):
    """Decide, for every record but the scratch copies, whether the catch-up
    regroups it (its grouping cache key differs from the stored one) and
    whether it marks its case report out of date (the coach last wrote it
    before the deploy, or an entry is on a card the coach no longer writes),
    with the grouping's cost estimated from the last grouping call in the
    model-calls ledger. Makes no model call and changes no record; saves the
    plan that `apply` and `undo` take, and prints one row per record."""
    found = (
        [find(diagram_id)]
        if diagram_id
        else Diagram.query.filter(Diagram.scratch.is_(False)).order_by(Diagram.id).all()
    )
    measured = per_call()
    cost = float(measured.cost_usd) if measured else None
    made = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    rows = [planned(diagram, deployed, cost) for diagram in found]
    folder = plans or pathlib.Path(current_app.instance_path) / PLANS
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"fd381-catchup-{made}.json"
    path.write_text(
        json.dumps(
            {
                "made": made,
                "deployed": deployed.isoformat(),
                "per_call_usd": cost,
                "diagrams": rows,
            },
            indent=2,
        )
    )
    columns = [
        "diagram",
        "owner",
        "regroup",
        "regroup_why",
        "mark",
        "mark_why",
        "estimate_usd",
    ]
    emit([{**row, "plan": str(path)} for row in rows], [*columns, "plan"], as_json)
    calls = sum(row["regroup_why"] == Regroup.Called for row in rows)
    said_to(
        as_json,
        f"saved {path}",
        (
            f"estimated ${cost * calls:.4f}: {calls} grouping calls at ${cost:.4f}, the "
            f"last grouping call in the ledger ({measured.model}, "
            f"{measured.created_at:%Y-%m-%d}); a refused answer is asked once more"
            if measured
            else f"{calls} grouping calls; no grouping call in the ledger to estimate from"
        ),
    )


plan = writes(plan)


def loaded(path: pathlib.Path) -> dict:
    saved = json.loads(path.read_text())
    if not {"made", "diagrams"} <= set(saved):
        raise click.ClickException(f"{path} is not a plan this command saved")
    return saved


def touched(saved: dict, diagram_id: int | None) -> list[dict]:
    """The plan's records the catch-up writes to, or only the one asked for."""
    entries = [e for e in saved["diagrams"] if e["regroup"] or e["mark"]]
    if diagram_id is None:
        return entries
    entries = [e for e in entries if e["diagram"] == diagram_id]
    if not entries:
        raise click.ClickException(f"the plan writes nothing to diagram {diagram_id}")
    return entries


def failed(turn_id: str) -> bool:
    """A grouping with no usable answer: the record keeps the clusters that
    pass. A stored cluster set aside before the call is not a failure."""
    return any(
        "setAside" not in o.detail
        for o in Observation.query.filter_by(
            turn_id=turn_id, kind=ObservationKind.ClusterFailed
        )
    )


def kept(diagram_id: int, turn_id: str) -> list[Change]:
    """The change rows written under a turn id and not taken back."""
    taken = record.undone(diagram_id)
    return [
        c
        for c in Change.query.filter_by(
            diagram_id=diagram_id, turn_id=turn_id
        ).order_by(Change.id)
        if c.id not in taken
    ]


def regrouped(diagram_id: int, turn_id: str) -> bool:
    """Whether this plan's regroup of the record already ran: every run ends
    in a change row or a failure written down."""
    return bool(kept(diagram_id, turn_id)) or (
        Observation.query.filter_by(
            turn_id=turn_id, kind=ObservationKind.ClusterFailed
        ).count()
        > 0
    )


def mark(diagram: Diagram, turn_id: str) -> None:
    """The case report out of date until its owner refreshes it: one change
    row of the catch-up's after its last card write, which `casereport.stale`
    reads."""
    record.apply(
        diagram.id, [], author=Author.Coach, turn_id=turn_id, user_id=diagram.user_id
    )


def state(entry: dict, made: str) -> dict:
    """One planned record as it stands: what this plan's writes came to."""
    diagram = find(entry["diagram"])
    turns = (TURN.format(diagram.id, made), marked(diagram.id, made))
    changes = [*kept(diagram.id, turns[0]), *kept(diagram.id, turns[1])]
    spent = (
        db.session.query(db.func.sum(ModelCall.cost_usd))
        .filter(ModelCall.turn_id == turns[0])
        .scalar()
    )
    lost = entry["regroup"] and failed(turns[0])
    ran = (
        not entry["regroup"]
        or regrouped(diagram.id, turns[0])
        or not clusters.behind(diagram.id, diagram.get_diagram_data())
    )
    shown = not entry["mark"] or bool(kept(diagram.id, turns[1]))
    return {
        "diagram": diagram.id,
        "owner": entry["owner"],
        "regroup": entry["regroup"],
        "mark": entry["mark"],
        "done": bool(ran and shown) and not lost,
        "failed": lost if entry["regroup"] else None,
        "groups": len(diagram.get_diagram_data().drawn_clusters()),
        "changes": [c.id for c in changes],
        "cost_usd": float(spent or 0),
    }


def owed(entry: dict, made: str) -> tuple[bool, bool]:
    """What of a planned record is still to write under this plan: its
    regroup, unless it ran or a turn regrouped the record since the plan; its
    mark, unless it is written."""
    diagram = find(entry["diagram"])
    regroup = (
        entry["regroup"]
        and not regrouped(diagram.id, TURN.format(diagram.id, made))
        and clusters.behind(diagram.id, diagram.get_diagram_data())
    )
    return regroup, entry["mark"] and not kept(diagram.id, marked(diagram.id, made))


def caught_up(entry: dict, made: str, regroup: bool, marks: bool) -> None:
    """One planned record's writes: the regroup through the function a coach
    turn runs, then the mark. A grouping the record refuses at the write
    keeps the groups already there, as a turn's does, and is written down as
    failed, so the rest of the plan goes on."""
    diagram = find(entry["diagram"])
    if regroup:
        turn_id = TURN.format(diagram.id, made)
        try:
            clusters.sync(
                diagram.id, turn_id=turn_id, user_id=diagram.user_id, force=True
            )
        except (clusters.ClusterError, record.Invalid) as refused:
            check = getattr(refused, "check", None)
            db.session.add(
                Observation(
                    diagram_id=diagram.id,
                    turn_id=turn_id,
                    kind=ObservationKind.ClusterFailed,
                    detail={
                        **({"check": check.value} if check else {}),
                        "detail": str(refused),
                        "fallback": False,
                        "reason": f"the record refused the regroup: {refused}",
                    },
                )
            )
        db.session.commit()
    if marks:
        mark(diagram, marked(diagram.id, made))


@click.command("apply")
@click.option(
    "--plan",
    "path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
    help="The plan file `plan` saved.",
)
@click.option("--diagram", "diagram_id", type=int, help="Only this record of the plan.")
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    help="Write at most this many of the plan's records not yet written.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON, not a table.")
def apply(path, diagram_id, limit, as_json):
    """Write a saved plan: regroup each record it names through
    clusters.sync(force=True), the function a coach turn runs, one grouping
    call each, a second when the first answer is refused, each in the
    model-calls ledger; and mark each case report it names out of date, so the
    owner's next tap rewrites it, never calling the refresh itself. Each
    record's writes are change rows that `undo` takes back. A record already
    written under this plan is not written again, so a run cut short, or run
    with --limit, is finished by running it again; a record a turn regrouped
    since the plan is done with no change row of the catch-up's. Each write
    moves the record's version, as a turn's does, so run it while no one is
    editing. Prints each planned record with whether it is done and failed,
    its change rows and the dollars its calls cost, then whether every stored
    result is what a turn stores and whether every record was written."""
    saved = loaded(path)
    entries = touched(saved, diagram_id)
    pending = [(e, owed(e, saved["made"])) for e in entries]
    pending = [(e, left) for e, left in pending if any(left)]
    for entry, left in pending[:limit] if limit else pending:
        caught_up(entry, saved["made"], *left)
    whole = {e["diagram"]: state(e, saved["made"]) for e in touched(saved, None)}
    rows = [whole[e["diagram"]] for e in entries]
    columns = [
        "diagram",
        "owner",
        "regroup",
        "mark",
        "done",
        "failed",
        "groups",
        "changes",
        "cost_usd",
    ]
    emit(rows, columns, as_json)
    done = sum(r["done"] for r in whole.values())
    lost = sum(bool(r["failed"]) for r in whole.values())
    said_to(
        as_json,
        f"same as a turn: yes, by construction: each regroup ran {SYNC}, the function a "
        "coach turn runs, on the record as stored, the person's answers and the same "
        "grouping call; only the turn id differs, and no monthly token cap is asked",
        f"completed: {len(whole)} planned, {done} done, {lost} failed, "
        f"{len(whole) - done - lost} not yet written",
    )


apply = writes(apply)


@click.command("undo")
@click.option(
    "--plan",
    "path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
    help="The plan file `apply` wrote.",
)
@click.option("--diagram", "diagram_id", type=int, help="Only this record of the plan.")
@click.option(
    "--yes", is_flag=True, help="Take them back; without it, only the preview."
)
@rows_option
def undo(path, diagram_id, yes):
    """Take back every change row `apply` wrote under a plan, record by
    record, newest first, each logged as its own undo naming the row: the
    clusters and the grouping cache key as they were, and the case report no
    longer out of date for the catch-up. A record changed since is left as it
    is and says why; the rest go on. Without --yes it prints what each row
    would take back and writes nothing."""
    saved = loaded(path)
    rows = []
    for entry in touched(saved, diagram_id):
        diagram = find(entry["diagram"])
        changes = [
            *kept(diagram.id, TURN.format(diagram.id, saved["made"])),
            *kept(diagram.id, marked(diagram.id, saved["made"])),
        ]
        if not changes:
            continue
        earlier, refused = record.undone(diagram.id), None
        try:
            back = record.taking_back(diagramjson.loads(diagram.data), changes)
            if yes:
                record.undo_changes(
                    diagram.id, [c.id for c in changes], author=Author.Coach
                )
        except record.Conflict as e:
            # rows are written one at a time, so a write between them can stop
            # the rest after some were taken back
            back = [(c, []) for c in sorted(changes, key=lambda c: -c.id)]
            refused = f"changed since it was written: {e}"
        done = record.undone(diagram.id) - earlier
        rows += [
            {
                "diagram": diagram.id,
                "change": change.id,
                "turn": change.turn_id,
                "undone": change.id in done,
                "taken_back": ", ".join(
                    f"{d['item_kind']} {d['item_id']} {said(d)}" for d in deltas
                ),
                "refused": None if change.id in done else refused,
            }
            for change, deltas in back
        ]
    return ["diagram", "change", "turn", "undone", "taken_back", "refused"], rows


undo = writes(undo)


@click.group("fd381-catchup")
def fd381_catchup():
    """Put every record on FD-381's grouping rules and mark each case report
    the coach wrote before them out of date, after the deploy carrying them
    and a backup: plan, then apply that plan; undo takes it back."""


for command in (plan, apply, undo):
    fd381_catchup.add_command(command)
