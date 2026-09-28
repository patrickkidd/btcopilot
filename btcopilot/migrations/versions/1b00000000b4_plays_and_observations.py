"""Every play-by-play told before this ends in the done event its turn never
wrote, so each statement carrying a turn has that turn's events. A play-by-play
keeps what it was told from in a digest, so the next explain of an unchanged
cluster opens it again with no call; plays told before this have none and are
told afresh once. Refused tool calls, a turn that used every step, turns that
failed or were declined, and play-by-plays refused or never told become kinds
of observation, and the groups Patrick rejects from the tuning queue get a
table [R-0542, R-0478, R-0517].

Revision ID: 1b00000000b4
Revises: 1b00000000b1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

from btcopilot import turnstore
from btcopilot.models.statement import StatementKind
from btcopilot.turnlog import TurnEventKind

revision = "1b00000000b4"
down_revision = "1b00000000b1"
branch_labels = None
depends_on = None

JSON = postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), "sqlite")

events = sa.table(
    "turn_events",
    sa.column("turn_id", sa.String),
    sa.column("discussion_id", sa.Integer),
    sa.column("seq", sa.Integer),
    sa.column("kind", sa.String),
    sa.column("payload", JSON),
    sa.column("created_at", sa.DateTime),
)
PLAYS = sa.text(
    """
    SELECT s.id, s.turn_id, s.discussion_id, s.created_at FROM statements s
     WHERE s.kind = :play AND s.turn_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM turn_events t WHERE t.turn_id = s.turn_id)
    """
).columns(created_at=sa.DateTime)
KINDS = (
    "tool_refused",
    "step_cap",
    "turn_failed",
    "turn_declined",
    "play_refused",
    "play_failed",
)


def upgrade():
    plays = op.get_bind().execute(PLAYS, {"play": StatementKind.Play.value}).all()
    op.bulk_insert(
        events,
        [
            {
                "turn_id": p.turn_id,
                "discussion_id": p.discussion_id,
                "seq": 1,
                "kind": TurnEventKind.Done.value,
                "payload": turnstore.done(p.id),
                "created_at": p.created_at,
            }
            for p in plays
        ],
    )
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("digest", sa.String(64), nullable=True))
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
