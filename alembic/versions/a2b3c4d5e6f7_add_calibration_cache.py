"""add_calibration_cache

Revision ID: a2b3c4d5e6f7
Revises: d2a5320cadc4
Create Date: 2026-03-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "d2a5320cadc4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discussions",
        sa.Column("calibration_report", sa.JSON(), nullable=True),
    )
    op.add_column(
        "discussions",
        sa.Column("calibration_advice", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("discussions", "calibration_advice")
    op.drop_column("discussions", "calibration_report")
