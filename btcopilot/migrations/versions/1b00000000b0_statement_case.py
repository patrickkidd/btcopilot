"""A play-by-play keeps the snapshots the coach told, so it opens again.

Revision ID: 1b00000000b0
Revises: 1b00000000af
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b0"
down_revision = "1b00000000af"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("told_case", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_column("told_case")
