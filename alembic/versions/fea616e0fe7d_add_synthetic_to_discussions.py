"""add_synthetic_to_discussions

Revision ID: fea616e0fe7d
Revises: 6a711267d4ed
Create Date: 2025-12-08 18:43:59.074830

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fea616e0fe7d"
down_revision = "6a711267d4ed"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discussions",
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "discussions",
        sa.Column("synthetic_persona", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("discussions", "synthetic_persona")
    op.drop_column("discussions", "synthetic")
