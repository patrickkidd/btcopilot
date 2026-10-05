"""Each user's IANA time zone, as the browser last sent it, so a scheduled
message and a turn with no zone of its own fall on the person's day.

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
