"""Each recorded quality value says who answered its run's model calls: the paid
API, or a Claude Code subscription. Every row before this was the API's.

Revision ID: 1b00000000b1
Revises: 1b00000000b0
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b1"
down_revision = "1b00000000b0"
branch_labels = None
depends_on = None

SOURCE = sa.Enum("api", "subscription", name="source")


def upgrade():
    SOURCE.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("quality_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source", SOURCE, nullable=False, server_default="api"))
        batch_op.alter_column("source", server_default=None)


def downgrade():
    with op.batch_alter_table("quality_runs", schema=None) as batch_op:
        batch_op.drop_column("source")
    SOURCE.drop(op.get_bind(), checkfirst=True)
