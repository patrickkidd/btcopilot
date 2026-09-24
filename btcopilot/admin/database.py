"""The chat app's own database chain, run from the installed app rather than a
checkout, so a fresh box needs only the wheel and its settings (R-0322)."""

from pathlib import Path

import click
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from flask import current_app
from sqlalchemy import create_engine

import btcopilot
from btcopilot.admin.guard import writes

CHAIN = Path(btcopilot.__file__).parent / "migrations"


def config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(CHAIN))
    cfg.set_main_option("sqlalchemy.url", current_app.config["SQLALCHEMY_DATABASE_URI"])
    return cfg


@click.group("db")
def database():
    """The chat database's own migration chain."""


@writes
@database.command("upgrade")
def db_upgrade():
    """Bring the database up to the newest revision, creating it from empty
    if it holds nothing yet."""
    command.upgrade(config(), "head")
    click.echo(f"at {current()}")


@database.command("current")
def db_current():
    """Which revision the database is at."""
    click.echo(current() or "empty")


def current() -> str | None:
    engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
