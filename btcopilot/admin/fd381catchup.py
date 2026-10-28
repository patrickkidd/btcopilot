"""The one pass that puts every diagram on FD-381's grouping rules and marks
each case report the coach wrote in the old shape out of date, so its owner's
next tap rewrites it, without waiting for the person's next turn [Oracle:
R-0772, R-0850]. `plan` decides and saves what the pass will do, with no model
call; `apply` does exactly that plan, each regroup through the same
`clusters.sync` a coach turn runs, written as change rows, and each mark as
the diagram's case_report_forced_out_of_date set true, kept beside the plan;
`undo` takes both back. The catch-up never calls the paid refresh of a
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
from btcopilot.schema import ClusterSource, DiagramData, ItemKind

TURN = "fd381-catchup:{}:{}"
PLANS = "fd381-catchup-plans"
SYNC = "clusters.sync(force=True)"
REFUSED = "the record refused the regroup"


class RegroupWhy(enum.StrEnum):
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


class MarkWhy(enum.StrEnum):
    Before = "a card on the report was last written before the deploy"
    After = "the coach wrote every card on the report after the deploy"
    # the page can show no mark on a report it cannot place in the change log
    Unlogged = "the change log holds no write of the report's cards"
    Unwritten = "the coach never wrote a report"


class Marked(enum.StrEnum):
    # kept before the flag is committed, so `undo` finds a mark cut short
    Marking = "marking"
    Set = "set"
    Cleared = "cleared"


OURS = (Marked.Marking, Marked.Set)


REGROUPS = (RegroupWhy.Called, RegroupWhy.Uncalled)
MARKS = (MarkWhy.Before,)


class Skipped(enum.StrEnum):
    Gone = "the diagram is gone"
    Owner = "its owner is not the plan's"
    Regrouped = "a turn regrouped it since the plan"
    Rewritten = "the coach wrote every card again since the plan"


def regrouping(diagram: Diagram, data: DiagramData) -> RegroupWhy:
    """Whether `sync` would group this diagram anew, and with a call: it
    calls the model only when the rules find a run or the person named when
    the most was going on (`clusters.detect_clusters`)."""
    if not clusters.behind(diagram, data):
        return RegroupWhy.Current
    if clusters.candidates(data) or clusters.told_ids(diagram.id, data):
        return RegroupWhy.Called
    if any(c.get("source") == ClusterSource.Model for c in data.drawn_clusters()):
        return RegroupWhy.Uncalled
    return RegroupWhy.Empty


def marking(diagram: Diagram, data: DiagramData, since: datetime.datetime) -> MarkWhy:
    """Whether a card on the report is still in the shape the coach wrote
    before the deploy: last written before it, or before the change log
    began. A report with no card the page shows was never written."""
    when = casereport.written(diagram.id, data)
    if not when:
        return MarkWhy.Unwritten
    logged_at = [w for w in when.values() if w]
    if not logged_at:
        return MarkWhy.Unlogged
    if len(logged_at) < len(when) or min(logged_at) < since:
        return MarkWhy.Before
    return MarkWhy.After


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


def owner_of(diagram: Diagram) -> str | None:
    return diagram.user.username if diagram.user else None


def planned(diagram: Diagram, since: datetime.datetime, cost: float | None) -> dict:
    data = diagram.get_diagram_data()
    regroup, mark = regrouping(diagram, data), marking(diagram, data, since)
    return {
        "diagram": diagram.id,
        "owner": owner_of(diagram),
        "regroup": regroup in REGROUPS,
        "regroup_why": regroup.value,
        "mark": mark in MARKS,
        "mark_why": mark.value,
        "estimate_usd": (
            None if cost is None else cost if regroup is RegroupWhy.Called else 0.0
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
    whether it marks its case report out of date (a card on it was last
    written before the deploy),
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
    calls = sum(row["regroup_why"] == RegroupWhy.Called for row in rows)
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


def kept_at(path: pathlib.Path) -> pathlib.Path:
    return path.with_suffix(".marks.json")


def kept(path: pathlib.Path) -> dict[str, str]:
    """The reports this plan's apply marked out of date, and those its undo
    cleared, by diagram id."""
    at = kept_at(path)
    return json.loads(at.read_text()) if at.exists() else {}


def keep(path: pathlib.Path, marks: dict[str, str]) -> None:
    kept_at(path).write_text(json.dumps(marks, indent=2))


def loaded(path: pathlib.Path) -> dict:
    saved = json.loads(path.read_text())
    if not {"made", "deployed", "diagrams"} <= set(saved):
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


def logged(diagram_id: int, turn_id: str) -> list[Change]:
    """Every change row written under a turn id, taken back since or not."""
    return (
        Change.query.filter_by(diagram_id=diagram_id, turn_id=turn_id)
        .order_by(Change.id)
        .all()
    )


def ran(diagram_id: int, turn_id: str) -> bool:
    """Whether this plan's regroup of the record ran, taken back since or
    not: every run ends in a change row or a failure written down, and a run
    stopped after a paid call left its ledger row. A regroup runs once per
    plan, so it is never paid for twice."""
    return bool(
        logged(diagram_id, turn_id)
        or Observation.query.filter_by(
            turn_id=turn_id, kind=ObservationKind.ClusterFailed
        ).count()
        or ModelCall.query.filter_by(turn_id=turn_id).count()
    )


def deployed_of(saved: dict) -> datetime.datetime:
    return datetime.datetime.fromisoformat(saved["deployed"])


def unowned(entry: dict, diagram: Diagram | None) -> Skipped | None:
    """Why a plan entry is not written at all: its diagram is gone, or is
    not the one the plan was made on, as a plan from another database."""
    if diagram is None:
        return Skipped.Gone
    if owner_of(diagram) != entry["owner"]:
        return Skipped.Owner
    return None


def owed(entry: dict, saved: dict, marks: dict[str, str]) -> tuple[bool, bool]:
    """What of a planned record is still to write under this plan, read just
    before its write: its regroup, unless it ran or a turn regrouped the
    record since the plan; its mark, unless this plan set or cleared it or
    the coach wrote every card again since the plan; a mark cut short is
    still owed."""
    diagram = db.session.get(Diagram, entry["diagram"])
    if unowned(entry, diagram):
        return False, False
    data = diagram.get_diagram_data()
    turn_id = TURN.format(diagram.id, saved["made"])
    regroup = (
        entry["regroup"]
        and not ran(diagram.id, turn_id)
        and clusters.behind(diagram, data)
    )
    mark = (
        entry["mark"]
        and marks.get(str(diagram.id)) in (None, Marked.Marking)
        and marking(diagram, data, deployed_of(saved)) in MARKS
    )
    return regroup, mark


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
                diagram.id,
                turn_id=turn_id,
                user_id=diagram.user_id,
                force=True,
                fresh=True,
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
                        "reason": REFUSED,
                    },
                )
            )
        db.session.commit()
    if marks:
        diagram.case_report_forced_out_of_date = True
        db.session.commit()


def changed_since(diagram_id: int, change: Change) -> bool:
    """Whether a cluster was written after the catch-up's regroup row, so
    the clusters stored are no longer the ones it wrote."""
    return any(
        d["item_kind"] == ItemKind.Cluster.value
        for later in Change.query.filter(
            Change.diagram_id == diagram_id, Change.id > change.id
        )
        for d in later.deltas
    )


def state(entry: dict, saved: dict, marks: dict[str, str]) -> dict:
    """One planned record as it stands: what this plan's writes came to, and
    whether its stored grouping is what `sync` stores on its own path: the
    grouping cache key sync computes now, and no cluster written by anything
    else after it."""
    made = saved["made"]
    diagram = db.session.get(Diagram, entry["diagram"])
    row = {
        "diagram": entry["diagram"],
        "owner": entry["owner"],
        "regroup": entry["regroup"],
        "mark": entry["mark"],
        "marked": marks.get(str(entry["diagram"])),
        "done": False,
        "failed": None,
        "undone": False,
        "same_as_turn": None,
        "groups": None,
        "changes": [],
        "cost_usd": 0.0,
        "skipped": None,
    }
    skipped = unowned(entry, diagram)
    if skipped:
        return {**row, "skipped": skipped.value}
    data = diagram.get_diagram_data()
    turn_id = TURN.format(diagram.id, made)
    regrouped = logged(diagram.id, turn_id)
    taken = record.undone(diagram.id)
    undone = (
        any(c.id in taken for c in regrouped)
        or marks.get(str(diagram.id)) == Marked.Cleared
    )
    notes, lost, regroup_done, same = [], None, True, None
    if entry["regroup"]:
        behind = clusters.behind(diagram, data)
        if ran(diagram.id, turn_id):
            lost = failed(turn_id) or not regrouped
        else:
            lost = False
            if not behind:
                notes.append(Skipped.Regrouped.value)
        regroup_done = not lost and (bool(regrouped) or not behind)
        if regroup_done or lost:
            same = (
                regroup_done
                and not undone
                and not behind
                and not (regrouped and changed_since(diagram.id, regrouped[-1]))
            )
    mark_done = True
    if entry["mark"] and marks.get(str(diagram.id)) in (None, Marked.Marking):
        mark_done = marking(diagram, data, deployed_of(saved)) not in MARKS
        if mark_done:
            notes.append(Skipped.Rewritten.value)
    spent = (
        db.session.query(db.func.sum(ModelCall.cost_usd))
        .filter(ModelCall.turn_id == turn_id)
        .scalar()
    )
    return {
        **row,
        "done": regroup_done and mark_done and not undone,
        "failed": lost,
        "undone": undone,
        "same_as_turn": same,
        "groups": len(data.drawn_clusters()),
        "changes": [c.id for c in regrouped],
        "cost_usd": float(spent or 0),
        "skipped": "; ".join(notes) or None,
    }


def same_as_turn(rows: list[dict]) -> str:
    """R-0772's first statement, record by record."""
    judged = [r for r in rows if r["same_as_turn"] is not None]
    unlike = [str(r["diagram"]) for r in judged if not r["same_as_turn"]]
    said = (
        f"same as a turn: yes for {len(judged) - len(unlike)} of {len(judged)} "
        f"regrouped records: each ran {SYNC}, the function a coach turn runs, on the "
        "record as stored and the person's answers, and holds the grouping cache key "
        "sync computes now"
    )
    if unlike:
        said += (
            f"; no for diagrams {', '.join(unlike)}: failed, refused, taken back or "
            "changed since"
        )
    return said


def outcome(row: dict) -> str:
    """What came of one planned record, one outcome each."""
    if row["skipped"] in (Skipped.Gone, Skipped.Owner):
        return "skipped"
    if row["undone"]:
        return "taken back"
    if row["failed"]:
        return "failed"
    return "done" if row["done"] else "not yet written"


def completed(rows: list[dict]) -> str:
    """R-0772's second statement: every record the plan writes to."""
    counts = [outcome(r) for r in rows]
    return f"completed: {len(rows)} planned, " + ", ".join(
        f"{counts.count(one)} {one}"
        for one in ("done", "failed", "taken back", "skipped", "not yet written")
    )


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
    model-calls ledger; and mark each case report it names out of date, its
    diagram's case_report_forced_out_of_date set true until a Refresh writes
    the cards, so the owner's next tap rewrites it, never calling the refresh
    itself. Each regroup is change rows and each mark is kept beside the
    plan, and `undo` takes both back. Each write is
    made once per plan, even after an undo, so a run cut short, or run with
    --limit, is finished by running it again, and no grouping is paid for
    twice. Just before each record's write it is read again: a record a turn
    regrouped since the plan is not regrouped, a report whose every card the
    coach wrote again since is not marked, and a record whose owner is not the plan's is not
    written at all. Each write moves the record's version, as a turn's does,
    so run it while no one is editing. Prints each planned record with what
    came of it, its change rows and the dollars its calls cost, then whether
    every stored grouping is what a turn stores and whether every record was
    written."""
    saved = loaded(path)
    entries = touched(saved, diagram_id)
    marks = kept(path)
    written = 0
    for entry in entries:
        if limit and written >= limit:
            break
        left = owed(entry, saved, marks)
        if any(left):
            if left[1]:
                marks[str(entry["diagram"])] = Marked.Marking
                keep(path, marks)
            caught_up(entry, saved["made"], *left)
            if left[1]:
                marks[str(entry["diagram"])] = Marked.Set
                keep(path, marks)
            written += 1
    whole = {e["diagram"]: state(e, saved, marks) for e in touched(saved, None)}
    columns = [
        "diagram",
        "owner",
        "regroup",
        "mark",
        "marked",
        "done",
        "failed",
        "undone",
        "same_as_turn",
        "groups",
        "changes",
        "cost_usd",
        "skipped",
    ]
    emit([whole[e["diagram"]] for e in entries], columns, as_json)
    rows = list(whole.values())
    said_to(as_json, same_as_turn(rows), completed(rows))


apply = writes(apply)


def taken_back(diagram: Diagram, changes: list[Change], yes: bool) -> list[dict]:
    """One group of a record's catch-up rows taken back, newest first, or
    only previewed; a value changed since stops the group and says so, with
    the rows it took back before the change marked undone."""
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
    return [
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


@click.command("undo")
@click.option(
    "--plan",
    "path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
    help="The plan file `plan` saved.",
)
@click.option("--diagram", "diagram_id", type=int, help="Only this record of the plan.")
@click.option(
    "--yes", is_flag=True, help="Take them back; without it, only the preview."
)
@rows_option
def undo(path, diagram_id, yes):
    """Take back what `apply` wrote under a plan, record by record: the case
    report's mark, its diagram's case_report_forced_out_of_date set back to
    false, which no later change can stop, then each change row of the
    regroup, newest first, each logged as its own undo naming the row, the
    clusters and the grouping cache key as they were. A regroup changed since is left as
    it is and says why; the rest go on. An undone plan is not written again;
    a new plan is. Without --yes it prints what each row would take back and
    writes nothing."""
    saved = loaded(path)
    marks = kept(path)
    rows = []
    for entry in touched(saved, diagram_id):
        diagram = db.session.get(Diagram, entry["diagram"])
        if diagram is None:
            continue
        if marks.get(str(diagram.id)) in OURS:
            if yes:
                diagram.case_report_forced_out_of_date = False
                db.session.commit()
                marks[str(diagram.id)] = Marked.Cleared
                keep(path, marks)
            rows.append(
                {
                    "diagram": diagram.id,
                    "change": None,
                    "turn": None,
                    "undone": yes,
                    "taken_back": "case_report_forced_out_of_date back to false",
                    "refused": None,
                }
            )
        taken = record.undone(diagram.id)
        changes = [
            c
            for c in logged(diagram.id, TURN.format(diagram.id, saved["made"]))
            if c.id not in taken
        ]
        if changes:
            rows += taken_back(diagram, changes, yes)
    return ["diagram", "change", "turn", "undone", "taken_back", "refused"], rows


undo = writes(undo)


@click.group("fd381-catchup")
def fd381_catchup():
    """Put every record on FD-381's grouping rules and mark each case report
    the coach wrote before them out of date, after the deploy carrying them
    and a backup: plan, then apply that plan; undo takes it back."""


for command in (plan, apply, undo):
    fd381_catchup.add_command(command)
