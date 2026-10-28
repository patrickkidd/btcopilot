"""Regrouping the records whose clusters are behind their events or the
person's answers to when the most was going on, so a fix to the grouping
reaches them without waiting for the person's next turn [Oracle: R-0772,
R-0844, R-0853]."""

import datetime
import enum

import click

from btcopilot import clusters, profile
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.llmutil import MissingKey
from btcopilot.models import Diagram, Observation, ObservationKind

TURN = "regroup:{}:{}"


class Why(enum.StrEnum):
    Changed = (
        "events or an answer about when the most was going on changed since the last "
        "grouping"
    )
    Ungrouped = "events and no groups"
    ByName = "nobody on the case is the person it belongs to: its periods are written about them by name"


def why(diagram: Diagram) -> Why | None:
    data = diagram.get_diagram_data()
    if not clusters.candidates(data) and not clusters.told_ids(diagram.id, data):
        return None
    if clusters.behind(diagram, data):
        return Why.Changed
    if not data.clusters:
        return Why.Ungrouped
    return None


@click.command("regroup")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--apply/--dry-run",
    default=False,
    help="Regroup the records listed; the default, --dry-run, lists them and makes "
    "no model call.",
)
@click.option(
    "--by-name",
    is_flag=True,
    help="Only the records nobody on is the person they belong to, whose periods "
    "are now written about that person by name, never to \"you\" [Oracle: R-0935].",
)
@rows_option
def regroup(diagram_id, apply, by_name):
    """Regroup each record whose events, or the person's answers to when the
    most was going on, changed since its last grouping, or that has events to
    group and no groups. The dry run lists them and makes no model call;
    --apply makes the grouping calls a turn makes, one or two per record, each
    in the model-calls ledger, and writes each record's new grouping as one
    change row that `diagrams undo` takes back: the app's periods as the answer
    returns them, the ones it leaves out set aside, and the periods the person
    named written as theirs. Before the call, a stored period of the app's
    that fails a check is set aside. A record whose answers are both refused
    keeps the stored periods that pass, sets aside the app's that fail, names
    nothing after its years, is not regrouped by a turn until its events or
    answers change, and `failed` says so."""
    columns = ["diagram", "why", "groups", "regrouped", "change", "failed"]
    found = [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for diagram in found:
        if by_name:
            data = diagram.get_diagram_data()
            hidden = diagram.scratch or diagram.deleted_at is not None
            if hidden or profile.named(diagram, data) is None or not data.clusters:
                continue
            reason = Why.ByName
        else:
            reason = why(diagram)
        if reason is None:
            continue
        row = {
            "diagram": diagram.id,
            "why": reason.value,
            # the clusters the page draws; one set aside stays stored, hidden
            "groups": len(diagram.get_diagram_data().drawn_clusters()),
            "regrouped": None,
            "change": None,
            "failed": None,
        }
        if apply:
            turn_id = TURN.format(diagram.id, stamp)
            try:
                done = clusters.sync(
                    diagram.id,
                    turn_id=turn_id,
                    user_id=diagram.user_id,
                    force=True,
                    fresh=True,
                )
            except MissingKey as missing:
                db.session.rollback()
                raise click.ClickException(str(missing))
            db.session.commit()
            row["regrouped"] = len(diagram.get_diagram_data().drawn_clusters())
            row["change"] = done.change.id if done else None
            row["failed"] = any(
                "setAside" not in o.detail
                for o in Observation.query.filter_by(
                    turn_id=turn_id, kind=ObservationKind.ClusterFailed
                )
            )
        rows.append(row)
    return columns, rows


regroup = writes(regroup)
