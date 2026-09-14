"""The one migration the branch adds, run against SQLite."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from mock import MagicMock, patch

from btcopilot.extensions import db

REVISION = (
    Path(__file__).resolve().parents[3]
    / "alembic/versions/e1f2a3b4c5d6_personal_chat_app.py"
)

RENAMED = {"diagram_changes", "diagram_interactions"}
REVIEW = {
    "review_cuts",
    "review_codings",
    "review_items",
    "review_votes",
    "review_rules",
}


def created_tables() -> set[str]:
    """Every table the revision creates, by running its upgrade against a
    SQLite connection with the operations recorded."""
    spec = importlib.util.spec_from_file_location("chat_app_revision", REVISION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    op = MagicMock()
    op.get_bind.return_value = engine.connect()
    with patch.object(module, "op", op):
        module.upgrade()
    return {call.args[0] for call in op.create_table.call_args_list}


def test_revision_creates_the_renamed_and_review_tables():
    created = created_tables()
    assert RENAMED | REVIEW <= created
    assert not {"changes", "interactions"} & created


def test_models_map_to_the_renamed_and_review_tables(flask_app):
    names = set(db.metadata.tables)
    assert RENAMED | REVIEW <= names
    assert not {"changes", "interactions"} & names


def test_author_enum_takes_review(flask_app):
    from btcopilot.personal.models import Author

    assert Author("review") is Author.Review


def test_discussion_kind_defaults_to_chat(flask_app, test_user):
    from btcopilot.personal.models import Discussion, DiscussionKind

    discussion = Discussion(user_id=test_user.id)
    db.session.add(discussion)
    db.session.commit()
    assert discussion.kind is DiscussionKind.Chat
