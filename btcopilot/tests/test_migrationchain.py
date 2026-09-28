"""The migration chain builds the app's database from empty on Postgres, the
database production runs. SQLite never checks that a table a foreign key
names exists, so only Postgres shows a table created before the one it
references."""

import pgserver
import pytest
import sqlalchemy as sa
from alembic import command

from btcopilot.admin.database import config
from btcopilot.tables import TABLES


@pytest.fixture
def postgres(tmp_path):
    with pgserver.get_server(tmp_path / "pg", cleanup_mode="delete") as server:
        yield server.get_uri()


def test_the_chain_builds_the_database_from_empty(flask_app, postgres):
    # R-0417
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = postgres
    with flask_app.app_context():
        command.upgrade(config(), "head")
    engine = sa.create_engine(postgres)
    tables = set(sa.inspect(engine).get_table_names())
    engine.dispose()
    assert TABLES <= tables
