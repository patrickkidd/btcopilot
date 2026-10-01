"""The single revision, run against SQLite."""

import importlib.util

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from mock import MagicMock, patch

from btcopilot.extensions import db
from btcopilot.tests.repo import REPO

REVISION = REPO / "btcopilot/migrations/versions/1b00000000aa_the_app_from_empty.py"
CUTS = REPO / "btcopilot/migrations/versions/1b00000000c0_model_call_purpose.py"

RENAMED = {"diagram_changes", "diagram_interactions"}
REVIEW = {
    "review_cuts",
    "review_codings",
    "review_items",
    "review_votes",
    "review_rules",
}


def revision(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def created_tables() -> set[str]:
    """Every table the revision creates, by running its upgrade against a
    SQLite connection with the operations recorded."""
    module = revision(REVISION)
    engine = sa.create_engine("sqlite://")
    op = MagicMock()
    op.get_bind.return_value = engine.connect()
    with patch.object(module, "op", op):
        module.upgrade()
    return {call.args[0] for call in op.create_table.call_args_list}


def test_revision_creates_the_renamed_and_review_tables():
    # R-0299, R-0296
    created = created_tables()
    assert RENAMED | REVIEW <= created
    assert not {"changes", "interactions"} & created


def test_models_map_to_the_renamed_and_review_tables(flask_app):
    # R-0299, R-0296
    names = set(db.metadata.tables)
    assert RENAMED | REVIEW <= names
    assert not {"changes", "interactions"} & names


def test_discussion_kind_defaults_to_chat(flask_app, test_user):
    # R-0281
    from btcopilot.models import Discussion, DiscussionKind

    discussion = Discussion(user_id=test_user.id)
    db.session.add(discussion)
    db.session.commit()
    assert discussion.kind is DiscussionKind.Chat


def test_a_cut_made_on_one_sitting_moves_to_its_familys_thread():
    # R-0296
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        for sql in (
            "CREATE TABLE diagrams (id INTEGER PRIMARY KEY)",
            "CREATE TABLE discussions (id INTEGER PRIMARY KEY, diagram_id INTEGER)",
            "CREATE TABLE review_cuts (id INTEGER PRIMARY KEY, discussion_id INTEGER"
            " NOT NULL REFERENCES discussions (id), start_statement_id INTEGER,"
            " end_statement_id INTEGER)",
            "CREATE INDEX ix_review_cuts_discussion_id ON review_cuts (discussion_id)",
            "INSERT INTO diagrams VALUES (7)",
            "INSERT INTO discussions VALUES (3, 7)",
            "INSERT INTO review_cuts VALUES (1, 3, 11, 12)",
        ):
            conn.execute(sa.text(sql))
        with Operations.context(MigrationContext.configure(conn)):
            revision(CUTS).cuts_on_thread()
        row = conn.execute(sa.text("SELECT * FROM review_cuts")).mappings().one()
    assert dict(row) == {
        "id": 1,
        "start_statement_id": 11,
        "end_statement_id": 12,
        "diagram_id": 7,
    }
