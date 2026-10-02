"""The migration chain builds the app's database from empty on Postgres, the
database production runs. The default suite runs the same chain on SQLite
(test_migrationchain.py, test_db.py)."""

import pytest
import sqlalchemy as sa
from alembic import command

from btcopilot.admin.database import config
from btcopilot.tables import TABLES

pytestmark = pytest.mark.integration


def test_the_chain_builds_the_database_from_empty(flask_app, postgres):
    # R-0417
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = postgres
    with flask_app.app_context():
        command.upgrade(config(), "head")
    engine = sa.create_engine(postgres)
    tables = set(sa.inspect(engine).get_table_names())
    engine.dispose()
    assert TABLES <= tables
