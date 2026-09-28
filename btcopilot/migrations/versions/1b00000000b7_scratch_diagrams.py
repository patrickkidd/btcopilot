"""A diagram a shadow turn writes on is marked scratch and never listed to the
user whose turn it copies [R-0589].

Revision ID: 1b00000000b7
Revises: 1b00000000b6
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000b7"
down_revision = "1b00000000b6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scratch", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )


def downgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.drop_column("scratch")
