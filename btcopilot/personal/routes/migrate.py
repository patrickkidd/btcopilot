"""Bring the configured database up to the current schema.

Two states, because the migration chain does not build a database from nothing:
it predates alembic here and never creates the `users` table, so `upgrade head`
on an empty file fails on the first revision. An empty database is therefore
built with create_all and stamped at head; a database that already carries data
is migrated.

Usage: FLASK_CONFIG=development FLASK_SQLALCHEMY_DATABASE_URI=sqlite:///<path>
       flask personal migrate
"""

import os
import traceback

import click
from alembic import command
from alembic.config import Config
from flask import current_app
from sqlalchemy import inspect

from btcopilot.personal.routes import bp
from btcopilot.extensions import db

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _config(uri: str) -> Config:
    config = Config(os.path.join(ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(ROOT, "alembic"))
    config.set_main_option("sqlalchemy.url", uri)
    # alembic/env.py reads the URI from the environment, not from the config.
    os.environ["FLASK_SQLALCHEMY_DATABASE_URI"] = uri
    return config


def bring_up_to_date(uri: str) -> str:
    """What it did: "created" a database that did not exist yet, or "migrated"
    one that did."""
    config = _config(uri)
    if inspect(db.engine).get_table_names():
        command.upgrade(config, "head")
        return "migrated"
    db.create_all()
    command.stamp(config, "head")
    return "created"


@bp.cli.command("migrate")
def migrate_command():
    """Create or migrate the database this app is configured for."""
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    click.echo(f"Bringing {uri} up to date")
    try:
        did = bring_up_to_date(uri)
    except Exception:
        # The flask CLI swallows what a command raises. Say it on both streams
        # so a caller that silences one still sees the failure.
        trace = traceback.format_exc()
        click.echo(trace, err=True)
        click.echo(f"FAILED: {trace.strip().splitlines()[-1]}")
        raise SystemExit(1)
    click.echo(did)
