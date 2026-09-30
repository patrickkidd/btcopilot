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
    calls = sa.table("model_calls", sa.column("purpose", PURPOSE), sa.column("turn_id", sa.String))
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


def downgrade():
    raise NotImplementedError("roll forward instead")
