"""A play-by-play keeps what it was told from, so the next explain of an
unchanged cluster opens it again with no call. Plays told before this have
none and are told afresh once.

Revision ID: 1b00000000b3
Revises: 1b00000000b2
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b3"
down_revision = "1b00000000b2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("digest", sa.String(64), nullable=True))


def downgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_column("digest")
