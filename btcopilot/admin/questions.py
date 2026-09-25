"""The questions the coach keeps: the one pass back over past sessions that
fills them in."""

import click

from btcopilot import questions
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.coachturn import MAX_STEPS
from btcopilot.models import Diagram, Discussion


@click.group("questions")
def questions_group():
    """The questions the coach keeps in each record."""


@writes
@questions_group.command("backfill")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option("--yes", is_flag=True, help="Go through the sessions; without it, only the preview.")
@rows_option
def questions_backfill(diagram_id, yes):
    """Go back once through every past session not yet gone through and fill in
    the questions asked in it. Makes model calls. Without --yes it prints what
    it would do and writes nothing."""
    diagrams = (
        [find(diagram_id)]
        if diagram_id
        else Diagram.query.filter(Diagram.id.in_(Discussion.query.with_entities(Discussion.diagram_id)))
        .order_by(Diagram.id)
        .all()
    )
    if yes:
        return questions.run(diagrams)
    rows = []
    for diagram in diagrams:
        todo, done = questions.pending(diagram)
        rows.append(
            {
                "diagram": diagram.id,
                "sessions_to_do": len(todo),
                "sessions_done": len(done),
                "estimated_model_calls": len(todo) * questions.CALLS_PER_SESSION,
                "most_model_calls": len(todo) * MAX_STEPS,
            }
        )
    return rows
