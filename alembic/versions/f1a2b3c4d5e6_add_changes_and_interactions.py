"""add changes and interactions

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-09-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f1a2b3c4d5e6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

AUTHOR = sa.Enum("user", "coach", "pro", name="author")
INTERACTION_KIND = sa.Enum("look", "say", "chip_tap", "play", name="interactionkind")
ITEM_KIND = sa.Enum(
    "person", "event", "pair_bond", "emotion", "cluster", "diagram", name="itemkind"
)


def upgrade():
    op.create_table(
        "changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "diagram_id",
            sa.Integer(),
            sa.ForeignKey("diagrams.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "statement_id", sa.Integer(), sa.ForeignKey("statements.id"), nullable=True
        ),
        sa.Column("turn_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("author", AUTHOR, nullable=False),
        sa.Column("deltas", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
    )
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "diagram_id",
            sa.Integer(),
            sa.ForeignKey("diagrams.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column(
            "statement_id", sa.Integer(), sa.ForeignKey("statements.id"), nullable=True
        ),
        sa.Column("kind", INTERACTION_KIND, nullable=False),
        sa.Column("item_kind", ITEM_KIND, nullable=False),
        sa.Column("item_id", sa.String(64), nullable=True),
    )


def downgrade():
    op.drop_table("interactions")
    op.drop_table("changes")
    bind = op.get_bind()
    ITEM_KIND.drop(bind, checkfirst=True)
    INTERACTION_KIND.drop(bind, checkfirst=True)
    AUTHOR.drop(bind, checkfirst=True)
