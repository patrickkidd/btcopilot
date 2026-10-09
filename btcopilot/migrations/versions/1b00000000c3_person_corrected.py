"""The observations kind for a turn whose notes say the person corrected the
coach. And a file attached to a message: its name and the text read from it,
the file itself not kept.

Revision ID: 1b00000000c3
Revises: 1b00000000c2
"""

import sqlalchemy as sa
from alembic import op

revision = "1b00000000c3"
down_revision = "1b00000000c2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("attachment_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("attachment_text", sa.Text(), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE observationkind ADD VALUE IF NOT EXISTS 'person_corrected'")


def downgrade():
    # Postgres cannot drop an enum label; the kind stays, unused.
    with op.batch_alter_table("statements", schema=None) as batch_op:
        batch_op.drop_column("attachment_text")
        batch_op.drop_column("attachment_name")
