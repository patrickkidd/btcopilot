"""Each person's time zone, so a follow-up the coach agreed to falls on their
own day and in their own waking hours rather than the server's.

The column holds the IANA zone name the browser last sent with a message
(America/Anchorage). Null until a message has carried one, until then follow-ups wait for the day in UTC (R-0758).

Revision ID: 1b00000000c2
Revises: 1b00000000c1
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000c2"
down_revision = "1b00000000c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("timezone")
