"""Which diagram the app is on, apart from which one is free

Switching families cannot write free_diagram_id: that column decides which
diagram is free of charge, so writing it to switch would hand a user a paid
diagram for nothing. Null means the app is on the free one.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""

import sqlalchemy as sa
from alembic import op

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("current_diagram_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_users_current_diagram_id", "diagrams", ["current_diagram_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_current_diagram_id", type_="foreignkey")
        batch.drop_column("current_diagram_id")
