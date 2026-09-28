"""What shows the coach or the app needing tuning: people or events that look
repeated, adds made before any read, refused tool calls, turns and
play-by-plays that failed. Each row is a candidate case for the coach's
regression evals; the queue groups them for Patrick to reject or take up."""

import click

from btcopilot import tuning
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.models import Observation, ObservationKind


@click.group()
def observations():
    """What shows the coach or the app needing tuning."""


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


@observations.command("queue")
@rows_option
def observation_queue():
    """The ten biggest groups of rows not yet rejected, test accounts left out:
    a kind and its reason with ids taken out, most often first."""
    return tuning.queue()


@writes
@observations.command("reject")
@click.argument("key")
@rows_option
def observation_reject(key):
    """Take the group with this key off the queue for good."""
    try:
        row = tuning.reject(key)
    except KeyError as error:
        raise click.ClickException(error.args[0])
    return [{"key": row.key, "kind": row.kind, "reason": row.reason}]
