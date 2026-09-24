"""What the watcher after each coach turn wrote down: people or events that
look repeated, and adds made before any read. Each row is a candidate case for
the coach's regression evals."""

import click

from btcopilot.admin.output import rows_option
from btcopilot.models import Observation, ObservationKind


@click.group()
def observations():
    """What the watcher after each coach turn noticed."""


@observations.command("list")
@click.option("--diagram", "diagram_id", type=int, help="Only one record's rows.")
@click.option(
    "--kind",
    type=click.Choice([kind.value for kind in ObservationKind]),
    help="Only one kind of row.",
)
@rows_option
def observation_list(diagram_id, kind):
    """Every row, oldest first."""
    query = Observation.query.order_by(Observation.id)
    if diagram_id:
        query = query.filter_by(diagram_id=diagram_id)
    if kind:
        query = query.filter_by(kind=ObservationKind(kind))
    return [
        {
            "id": row.id,
            "diagram_id": row.diagram_id,
            "turn_id": row.turn_id,
            "kind": row.kind.value,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in query.all()
    ]
