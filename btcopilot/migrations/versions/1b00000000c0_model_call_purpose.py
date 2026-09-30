"""Each model call says what it was for, so shadow spend is its own category
and is kept out of the cost panels for the people the coach talks to. Rows
from before the column are read from their turn id.

Revision ID: 1b00000000c0
Revises: 1b00000000bf
"""

from alembic import op
import sqlalchemy as sa

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
    name="purpose",
)


def upgrade():
    PURPOSE.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("model_calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purpose", PURPOSE, nullable=True))
    op.execute("""
        UPDATE model_calls SET purpose = CASE
            WHEN turn_id LIKE 'shadow-%' THEN 'shadow'::purpose
            WHEN turn_id LIKE 'backfill:%' OR turn_id LIKE 'impression-backfill:%'
                THEN 'backfill'::purpose
            ELSE 'coach'::purpose
        END
        """)
    with op.batch_alter_table("model_calls", schema=None) as batch_op:
        batch_op.alter_column("purpose", nullable=False)


def downgrade():
    raise NotImplementedError("roll forward instead")
