"""A real turn can be run again on a second model over a scratch copy of the
record, and what that model said, called and spent is kept for comparison; the
scratch diagram is never listed to the user whose turn it copies [R-0596].
Patrick picks the better of two replies to the same words without knowing
which model wrote either, and each pick is kept per pair [R-0599].

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

JSON = postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), "sqlite")
SOURCE = sa.Enum("shadow", "replay", name="picksource")
CHOICE = sa.Enum("left", "right", "tie", name="pickchoice")


def upgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scratch", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

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
        sa.Column("tool_calls", JSON, nullable=True),
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

    op.create_table(
        "model_picks",
        sa.Column("pair", sa.String(length=64), nullable=False),
        sa.Column("source", SOURCE, nullable=False),
        sa.Column("left_ref", JSON, nullable=False),
        sa.Column("right_ref", JSON, nullable=False),
        sa.Column("choice", CHOICE, nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair"),
    )
    with op.batch_alter_table("model_picks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_model_picks_id"), ["id"])


def downgrade():
    op.drop_table("model_picks")
    CHOICE.drop(op.get_bind(), checkfirst=True)
    SOURCE.drop(op.get_bind(), checkfirst=True)
    op.drop_table("shadow_turns")
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.drop_column("scratch")
