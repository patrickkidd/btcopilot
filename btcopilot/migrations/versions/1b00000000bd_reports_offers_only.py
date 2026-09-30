"""The reports table keeps only what the coach offers from the conversation:
an error in the code is Grafana's, so the rows that held one, sandbox data
only, go, and so do the columns that held it and the count of its repeats.

Revision ID: 1b00000000bd
Revises: 1b00000000bc
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000bd"
down_revision = "1b00000000bc"
branch_labels = None
depends_on = None

SOURCE = sa.Enum("page", "server", "worker", name="reportsource")
DROPPED = ("count", "source", "signature", "error", "frames", "request_id")


def upgrade():
    op.execute("DELETE FROM reports WHERE error IS NOT NULL")
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.drop_constraint("report_feedback_carries_no_fault", type_="check")
        batch_op.drop_index(batch_op.f("ix_reports_signature"))
        batch_op.drop_index(batch_op.f("ix_reports_request_id"))
        for column in DROPPED:
            batch_op.drop_column(column)
    SOURCE.drop(op.get_bind(), checkfirst=True)


def downgrade():
    raise NotImplementedError("roll forward instead")
