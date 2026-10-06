"""Regrouping the records whose clusters are behind their events, so a fix to
the grouping reaches them without waiting for the person's next turn
[Oracle: R-0772, R-0780]."""

import datetime
import enum

import click

from btcopilot import clusters
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.models import Diagram, Observation, ObservationKind

TURN = "regroup:{}:{}"


class Why(enum.StrEnum):
    Changed = "events changed since the last grouping"
    Ungrouped = "events and no groups"


def why(diagram: Diagram) -> Why | None:
    data = diagram.get_diagram_data()
    if not clusters.candidates(data):
        return None
    if clusters.behind(data):
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
@rows_option
def regroup(diagram_id, apply):
    """Regroup each record whose events changed since its last grouping, or that
    has events to group and no groups. The dry run lists them and makes no model
    call; --apply makes the grouping calls a turn makes, one or two per record,
    each in the model-calls ledger, and writes each record's new grouping as one
    change row that `diagrams undo` takes back. A record whose answers are both
    refused gets the rules' groups under their years, and `failed` says so."""
    columns = ["diagram", "why", "groups", "regrouped", "change", "failed"]
    found = [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for diagram in found:
        reason = why(diagram)
        if reason is None:
            continue
        row = {
            "diagram": diagram.id,
            "why": reason.value,
            "groups": len(diagram.get_diagram_data().clusters),
            "regrouped": None,
            "change": None,
            "failed": None,
        }
        if apply:
            turn_id = TURN.format(diagram.id, stamp)
            done = clusters.sync(
                diagram.id, turn_id=turn_id, user_id=diagram.user_id, force=True
            )
            db.session.commit()
            row["regrouped"] = len(diagram.get_diagram_data().clusters)
            row["change"] = done.change.id if done else None
            row["failed"] = bool(
                Observation.query.filter_by(
                    turn_id=turn_id, kind=ObservationKind.ClusterFailed
                ).count()
            )
        rows.append(row)
    return columns, rows


regroup = writes(regroup)
