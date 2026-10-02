"""The migration chain never makes a table before the one its foreign key
names. Postgres refuses that and SQLite lets it by, so the chain is run on
SQLite, as every local test is, and each table is checked as it is made. What
the chain builds is compared with the models in test_db.py."""

import sqlalchemy as sa
from alembic import command

from btcopilot.admin.database import config
from btcopilot.tables import tables


def dangling(cursor) -> set[str]:
    """Each foreign key that names a table not made yet."""
    made = {
        row[0]
        for row in cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    return {
        f"{table}.{key[3]} -> {key[2]}"
        for table in made
        for key in cursor.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
        if key[2] not in made
    }


def test_no_table_is_made_before_one_its_foreign_key_names(flask_app, tmp_path):
    # R-0417
    early = set()

    def check(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("CREATE TABLE"):
            early.update(dangling(cursor))

    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'chain.db'}"
    sa.event.listen(sa.engine.Engine, "after_cursor_execute", check)
    with flask_app.app_context():
        command.upgrade(config(), "head")
    sa.event.remove(sa.engine.Engine, "after_cursor_execute", check)
    # Two tables that name each other cannot both come first: the models mark
    # those keys, and Postgres is handed them after both tables are made.
    cycles = {
        f"{table.name}.{key.parent.name} -> {key.column.table.name}"
        for table in tables()
        for key in table.foreign_keys
        if key.constraint.use_alter
    }
    assert early - cycles == set()
