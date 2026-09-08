"""Record whether a session's title was given by hand

The sessions sheet marks a hand-renamed session with a pencil. The title alone
cannot say who wrote it, so the rename endpoint stamps this.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discussions",
        sa.Column(
            "title_set_by_user",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("discussions", "title_set_by_user")
