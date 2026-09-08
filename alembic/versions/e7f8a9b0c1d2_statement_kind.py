"""Statement kind and the stretch a play-by-play narrates

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""

import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None

KIND = sa.Enum("turn", "play", name="statementkind")


def upgrade():
    KIND.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "statements",
        sa.Column("kind", KIND, nullable=False, server_default="turn"),
    )
    op.add_column("statements", sa.Column("cluster_id", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("statements", "cluster_id")
    op.drop_column("statements", "kind")
    KIND.drop(op.get_bind(), checkfirst=True)
