"""Every play-by-play told before this ends in the done event its turn never
wrote, so each statement carrying a turn has that turn's events.

Revision ID: 1b00000000b2
Revises: 1b00000000b1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

from btcopilot import turnstore
from btcopilot.models.statement import StatementKind
from btcopilot.turnlog import TurnEventKind

revision = "1b00000000b2"
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


def downgrade():
    op.execute(
        sa.text(
            """
            DELETE FROM turn_events WHERE turn_id IN
              (SELECT turn_id FROM statements WHERE kind = :play AND turn_id IS NOT NULL)
            """
        ).bindparams(play=StatementKind.Play.value)
    )
