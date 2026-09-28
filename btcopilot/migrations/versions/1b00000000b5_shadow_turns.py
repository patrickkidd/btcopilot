"""A real turn can be run again on a second model over a copy of the record,
and what that model said, called and spent is kept for comparison [R-0589].

Revision ID: 1b00000000b5
Revises: 1b00000000b4
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "1b00000000b5"
down_revision = "1b00000000b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shadow_turns",
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("diagram_id", sa.Integer(), nullable=False),
        sa.Column("discussion_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["discussion_id"], ["discussions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["statements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("shadow_turns", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_shadow_turns_id"), ["id"])
        batch_op.create_index(
            batch_op.f("ix_shadow_turns_turn_id"), ["turn_id"], unique=True
        )
        batch_op.create_index(batch_op.f("ix_shadow_turns_user_id"), ["user_id"])


def downgrade():
    op.drop_table("shadow_turns")
