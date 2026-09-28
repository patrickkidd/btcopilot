"""The quality dashboard's recorded runs, loaded by every release, and the
replay of a discussion on another model, scored."""

from decimal import Decimal
from pathlib import Path

import click
from flask import current_app

from btcopilot import quality as runs
from btcopilot import replayscore
from btcopilot.admin.guard import writes
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion

PRODUCTION = "production"


@click.group()
def quality():
    """The recorded runs the quality dashboard reads."""


@writes
@quality.command("load")
@click.argument("root", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path))
def quality_load(root):
    """Load every recorded run under a checkout or the image into the table,
    updating the ones already there."""
    click.echo(f"{runs.load(root)} values loaded")


@writes
@quality.command("replay")
@click.argument("discussion_id", type=int)
@click.argument("model")
@click.argument("reference_diagram_id", type=int)
@click.option(
    "--cap",
    type=Decimal,
    default=Decimal(5),
    show_default=True,
    help="Dollars; no turn starts past it.",
)
def quality_replay(discussion_id, model, reference_diagram_id, cap):
    """Replay a session's words on MODEL onto a scratch record, score it
    against the record Patrick corrected, and append one ledger line. Never on
    the box: it spends on the model and writes scratch records."""
    if current_app.config["CONFIG"] == PRODUCTION:
        raise click.UsageError("replays run in the sandbox, never on production")
    discussion = db.session.get(Discussion, discussion_id)
    reference = db.session.get(Diagram, reference_diagram_id)
    if discussion is None or reference is None:
        raise click.UsageError("no such session or reference diagram")
    row = replayscore.replay(discussion, model, reference, cap=cap)
    click.echo(
        f"{row['requested']} as {row['model']}: {row['turns']} turns, ${row['cost']:.4f}"
    )
    click.echo(
        f"scratch diagram {row['scratch_diagram_id']}, session {row['scratch_discussion_id']}"
    )
    for part in ("scores", "faults"):
        for name, value in row[part].items():
            click.echo(f"  {name:<18} {'-' if value is None else value}")
