"""Every diagram gets a public id: the short, random, opaque id it is named by
in the app's addresses and in the page's reads, so its row number never leaves
the server. Each diagram already in the table is given one here.

Revision ID: 1b00000000c4
Revises: 1b00000000c3
"""

import secrets

import sqlalchemy as sa
from alembic import op

revision = "1b00000000c4"
down_revision = "1b00000000c3"
branch_labels = None
depends_on = None

# The same letters and length as btcopilot.models.diagram.new_public_id, kept
# here so the revision reads the same whatever the model becomes.
LETTERS = "abcdefghjkmnpqrstuvwxyz23456789"
LENGTH = 10


def upgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.add_column(sa.Column("public_id", sa.String(length=12), nullable=True))
    diagrams = sa.table(
        "diagrams", sa.column("id", sa.Integer), sa.column("public_id", sa.String)
    )
    conn = op.get_bind()
    given: set[str] = set()
    for (diagram_id,) in conn.execute(sa.select(diagrams.c.id).order_by(diagrams.c.id)):
        key = "".join(secrets.choice(LETTERS) for _ in range(LENGTH))
        while key in given:
            key = "".join(secrets.choice(LETTERS) for _ in range(LENGTH))
        given.add(key)
        conn.execute(
            diagrams.update().where(diagrams.c.id == diagram_id).values(public_id=key)
        )
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.alter_column("public_id", existing_type=sa.String(length=12), nullable=False)
        batch_op.create_index("ix_diagrams_public_id", ["public_id"], unique=True)


def downgrade():
    with op.batch_alter_table("diagrams", schema=None) as batch_op:
        batch_op.drop_index("ix_diagrams_public_id")
        batch_op.drop_column("public_id")
