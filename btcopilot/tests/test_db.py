"""The chat app's own database: the chain builds it from empty, and what it
builds is what the models declare.

A column added to a chat model with no matching revision fails here rather than
turning up missing on a fresh database.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from btcopilot import tables
from btcopilot.extensions import db

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

PRO_ONLY = {"activations", "feedbacks", "machines", "reconciliation_notes", "sessions"}


def chain_db(path) -> str:
    url = f"sqlite:///{path}"
    config = Config(os.path.join(ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(ROOT, "btcopilot", "migrations"))
    os.environ["FLASK_SQLALCHEMY_DATABASE_URI"] = url
    command.upgrade(config, "head")
    return url


def shape(url: str) -> dict:
    engine = create_engine(url)
    inspector = inspect(engine)
    names = set(inspector.get_table_names()) - {"alembic_version"}
    return {
        name: sorted(column["name"] for column in inspector.get_columns(name))
        for name in names
    }


@pytest.fixture
def chain(tmp_path):
    before = os.environ.get("FLASK_SQLALCHEMY_DATABASE_URI")
    yield chain_db(tmp_path / "chain.db")
    if before is None:
        del os.environ["FLASK_SQLALCHEMY_DATABASE_URI"]
    else:
        os.environ["FLASK_SQLALCHEMY_DATABASE_URI"] = before


def test_chain_builds_the_chat_tables_and_no_others(chain):
    # R-0327
    assert set(shape(chain)) == set(tables.TABLES)


CHAT_PACKAGES = ("btcopilot.review", "btcopilot.personal", "btcopilot.auth", "btcopilot.admin")


def test_every_chat_model_is_in_the_chain():
    # no ruling
    """A model in a chat-app package whose table the chain does not build is a
    table that exists on the sandbox by hand and on a fresh server not at all,
    which is how review_notes went missing."""
    owned = {
        mapper.local_table.name
        for mapper in db.Model.registry.mappers
        if mapper.class_.__module__.startswith(CHAT_PACKAGES)
    }
    assert owned - set(tables.TABLES) == set()


def test_chain_matches_what_the_models_declare(chain, tmp_path):
    # no ruling
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")
    tables.create_all(engine)
    assert shape(chain) == shape(str(engine.url))


def test_every_foreign_key_points_inside_the_chat_database():
    # R-0327
    outside = {
        f"{table.name}.{fk.parent.name} -> {fk.column.table.name}"
        for table in tables.tables()
        for fk in table.foreign_keys
        if fk.column.table.name not in tables.TABLES
    }
    assert not outside


def test_the_pro_desktop_tables_are_gone():
    # R-0327
    assert not tables.TABLES & PRO_ONLY
