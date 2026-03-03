"""add_indexes_to_personal_models_fks

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-03-02 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_discussions_user_id"), "discussions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_discussions_diagram_id"), "discussions", ["diagram_id"], unique=False
    )
    op.create_index(
        op.f("ix_statements_discussion_id"),
        "statements",
        ["discussion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_statements_speaker_id"), "statements", ["speaker_id"], unique=False
    )
    op.create_index(
        op.f("ix_speakers_discussion_id"), "speakers", ["discussion_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_speakers_discussion_id"), table_name="speakers")
    op.drop_index(op.f("ix_statements_speaker_id"), table_name="statements")
    op.drop_index(op.f("ix_statements_discussion_id"), table_name="statements")
    op.drop_index(op.f("ix_discussions_diagram_id"), table_name="discussions")
    op.drop_index(op.f("ix_discussions_user_id"), table_name="discussions")
