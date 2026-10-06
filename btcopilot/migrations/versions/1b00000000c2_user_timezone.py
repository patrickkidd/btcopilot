"""Each user's IANA time zone, as the browser last sent it, so a scheduled
message and a turn with no zone of its own fall on the person's day. And the
observations kinds for a refused grouping answer and a turn whose answers were
all refused.

Revision ID: 1b00000000c2
Revises: 1b00000000c1
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000c2"
down_revision = "1b00000000c1"
branch_labels = None
depends_on = None


KINDS = ("cluster_refused", "cluster_failed")


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for kind in KINDS:
                op.execute(
                    f"ALTER TYPE observationkind ADD VALUE IF NOT EXISTS '{kind}'"
                )


def downgrade():
    # Postgres cannot drop an enum label; the two kinds stay, unused.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("timezone")
