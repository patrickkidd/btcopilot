"""Bringing the old Pro accounts and records across, once."""

import click

from btcopilot.admin import proimport
from btcopilot.admin.output import rows_option
from btcopilot.admin.guard import writes


@click.group()
def imports():
    """The one-time read of the old Pro database."""


@imports.command("dry-run")
@click.argument("dump")
@rows_option
def import_dry_run(dump):
    """Read the dump, or a live connection string, and report what would come
    across, writing nothing."""
    return proimport.dry_run(dump)


@writes
@imports.command("run")
@click.argument("dump")
@click.confirmation_option(prompt="This writes accounts and records. Go ahead?")
@rows_option
def import_run(dump):
    """Read the dump and write the accounts and records it holds."""
    return proimport.run(dump)
