"""add_version_to_diagrams

Revision ID: 6a711267d4ed
Revises: fc24860407c0
Create Date: 2025-11-22 07:51:08.807026

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6a711267d4ed"
down_revision = "fc24860407c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "diagrams",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_column("diagrams", "version")
