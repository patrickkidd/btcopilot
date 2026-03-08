"""rename prompt_used to meta json on feedbacks

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-03-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    # If prompt_used already exists (dev), migrate it to meta JSON
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("feedbacks")]

    if "prompt_used" in columns and "meta" not in columns:
        op.add_column("feedbacks", sa.Column("meta", sa.JSON(), nullable=True))
        op.execute(
            "UPDATE feedbacks SET meta = json_build_object('prompt', prompt_used) "
            "WHERE prompt_used IS NOT NULL"
        )
        op.drop_column("feedbacks", "prompt_used")
    elif "meta" not in columns:
        op.add_column("feedbacks", sa.Column("meta", sa.JSON(), nullable=True))


def downgrade():
    op.add_column("feedbacks", sa.Column("prompt_used", sa.Text(), nullable=True))
    op.execute(
        "UPDATE feedbacks SET prompt_used = meta->>'prompt' "
        "WHERE meta IS NOT NULL AND meta->>'prompt' IS NOT NULL"
    )
    op.drop_column("feedbacks", "meta")
