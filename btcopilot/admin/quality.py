"""The quality dashboard's recorded runs, loaded by every release."""

from pathlib import Path

import click

from btcopilot import quality as runs
from btcopilot.admin.guard import writes


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
