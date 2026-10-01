"""Each model call says what it was for, so shadow spend is its own category
and is kept out of the cost panels for the people the coach talks to. Rows
from before the column are read from their turn id. A call about no record
(ratifying a cut, judging a thread, transcribing a recording) has no diagram.

A cut is a first and a last line in the family's thread rather than in one
sitting: it names the family, and each line names its own sitting. A cut
already made names its sitting's family and keeps its two lines.
Each replay pass is kept in its own table so a key is never paid for twice.

Revision ID: 1b00000000c0
Revises: 1b00000000bf
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "1b00000000c0"
down_revision = "1b00000000bf"
branch_labels = None
depends_on = None

PURPOSE = sa.Enum(
    "coach",
    "shadow",
    "proactive",
    "replay",
    "play",
    "backfill",
    "summary",
    "cluster",
    "scribe",
    "ratify",
    "judge",
    "transcribe",
    name="purpose",
)
# Production ran this revision before these were in the list; its type gains
# them here, its diagram column drops NOT NULL, and its cuts move to the
# family's thread by hand (FD-366 box statement), on the next rollout.
ADDED = ("cluster", "scribe", "ratify", "judge", "transcribe")
# quality_runs created this type.
SOURCE = sa.Enum("api", "subscription", name="source").with_variant(
    postgresql.ENUM(name="source", create_type=False), "postgresql"
)


def upgrade():
    bind = op.get_bind()
    PURPOSE.create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        for value in ADDED:
            op.execute(f"ALTER TYPE purpose ADD VALUE IF NOT EXISTS '{value}'")
    with op.batch_alter_table("model_calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purpose", PURPOSE, nullable=True))
        batch_op.alter_column("diagram_id", existing_type=sa.Integer(), nullable=True)
    calls = sa.table(
        "model_calls", sa.column("purpose", PURPOSE), sa.column("turn_id", sa.String)
    )
    op.execute(
        calls.update().values(
            purpose=sa.case(
                (calls.c.turn_id.like("shadow-%"), sa.cast("shadow", PURPOSE)),
                (
                    sa.or_(
                        calls.c.turn_id.like("backfill:%"),
                        calls.c.turn_id.like("impression-backfill:%"),
                    ),
                    sa.cast("backfill", PURPOSE),
                ),
                else_=sa.cast("coach", PURPOSE),
            )
        )
    )
    with op.batch_alter_table("model_calls", schema=None) as batch_op:
        batch_op.alter_column("purpose", nullable=False)
    cuts_on_thread()


def cuts_on_thread():
    with op.batch_alter_table("review_cuts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("diagram_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE review_cuts SET diagram_id = (SELECT discussions.diagram_id "
        "FROM discussions WHERE discussions.id = review_cuts.discussion_id)"
    )
    with op.batch_alter_table("review_cuts", schema=None) as batch_op:
        batch_op.alter_column("diagram_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index("ix_review_cuts_discussion_id")
        batch_op.drop_column("discussion_id")
        batch_op.create_index("ix_review_cuts_diagram_id", ["diagram_id"])
        batch_op.create_foreign_key(
            "review_cuts_diagram_id_fkey", "diagrams", ["diagram_id"], ["id"]
        )
    op.create_table(
        "replay_passes",
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("thinking", sa.String(length=16), nullable=False),
        sa.Column("prompt", sa.String(length=16), nullable=False),
        sa.Column("case", sa.Text(), nullable=True),
        sa.Column("turns", sa.Integer(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("people", sa.Float(), nullable=True),
        sa.Column("events", sa.Float(), nullable=True),
        sa.Column("pair_bonds", sa.Float(), nullable=True),
        sa.Column("clusters", sa.Float(), nullable=True),
        sa.Column("variables", sa.Float(), nullable=True),
        sa.Column("overall", sa.Float(), nullable=True),
        sa.Column("release", sa.String(length=64), nullable=True),
        sa.Column("source", SOURCE, nullable=False),
        sa.Column("scratch_diagram_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("replay_passes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_replay_passes_id"), ["id"])
        batch_op.create_index(batch_op.f("ix_replay_passes_case"), ["case"])


def downgrade():
    raise NotImplementedError("roll forward instead")
