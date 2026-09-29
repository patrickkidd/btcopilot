"""Messages the coach writes first: a pattern the record just made visible, or
a follow-up the person agreed to."""

import click

from btcopilot import proactive
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option


@click.group("proactive")
def proactive_group():
    """Messages the coach writes before the person does."""


@writes
@proactive_group.command("run")
@click.option(
    "--dry-run", is_flag=True, help="Print what would be sent; keep and send nothing."
)
@rows_option
def proactive_run(dry_run):
    """Write and send at most one message per person, within their budget. The
    words come from the model even on a dry run. Each person nothing went to
    gets the reason instead."""
    return proactive.run(dry_run=dry_run)
