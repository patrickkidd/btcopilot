"""A diagram's case report marked out of date by the FD-381 catch-up, apart
from the change-date check, until a Refresh writes its cards.

Revision ID: 1b00000000c4
Revises: 1b00000000c3
"""

import sqlalchemy as sa
from alembic import op

revision = "1b00000000c4"
down_revision = "1b00000000c3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "case_report_forced_out_of_date",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.drop_column("case_report_forced_out_of_date")
