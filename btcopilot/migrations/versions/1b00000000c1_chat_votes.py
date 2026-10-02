"""A pick made in the chat records whether each reply was acceptable at all,
and a coach turn and a shadow turn each name the prompt version they ran on.

Revision ID: 1b00000000c1
Revises: 1b00000000c0
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000c1"
down_revision = "1b00000000c0"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE picksource ADD VALUE IF NOT EXISTS 'chat'")
    with op.batch_alter_table("model_picks", schema=None) as batch_op:
        for side in ("left", "right"):
            batch_op.add_column(
                sa.Column(f"{side}_acceptable", sa.Boolean(), nullable=True)
            )
    for table in ("statements", "shadow_turns"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("prompt_version", sa.String(length=16), nullable=True)
            )


def downgrade():
    raise NotImplementedError("roll forward instead")
