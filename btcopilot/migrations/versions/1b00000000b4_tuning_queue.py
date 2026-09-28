"""Refused tool calls, a turn that used every step, turns that failed or were
declined, and play-by-plays refused or never told become kinds of observation,
and the groups Patrick rejects from the tuning queue get a table [R-0517]. Six
enum labels and one table are added; no row is read or written.

Revision ID: 1b00000000b4
Revises: 1b00000000b3
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b4"
down_revision = "1b00000000b3"
branch_labels = None
depends_on = None

KINDS = (
    "tool_refused",
    "step_cap",
    "turn_failed",
    "turn_declined",
    "play_refused",
    "play_failed",
)


def upgrade():
    op.create_table(
        "observation_rejects",
        sa.Column("key", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    with op.batch_alter_table("observation_rejects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_observation_rejects_id"), ["id"])
    # SQLite stores these enums as plain strings with no list to extend.
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for kind in KINDS:
            op.execute(f"ALTER TYPE observationkind ADD VALUE IF NOT EXISTS '{kind}'")


def downgrade():
    raise NotImplementedError(
        "Postgres cannot drop an enum label: roll forward instead"
    )
