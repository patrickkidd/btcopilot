"""Patrick picks the better of two replies to the same words without knowing
which model wrote either, and each pick is kept per pair [R-0592].

Revision ID: 1b00000000b6
Revises: 1b00000000b5
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "1b00000000b6"
down_revision = "1b00000000b5"
branch_labels = None
depends_on = None

SOURCE = sa.Enum("shadow", "replay", name="picksource")
CHOICE = sa.Enum("left", "right", "tie", name="pickchoice")
REF = postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), "sqlite")


def upgrade():
    op.create_table(
        "model_picks",
        sa.Column("pair", sa.String(length=64), nullable=False),
        sa.Column("source", SOURCE, nullable=False),
        sa.Column("left_ref", REF, nullable=False),
        sa.Column("right_ref", REF, nullable=False),
        sa.Column("choice", CHOICE, nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair"),
    )
    with op.batch_alter_table("model_picks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_model_picks_id"), ["id"])


def downgrade():
    op.drop_table("model_picks")
    CHOICE.drop(op.get_bind(), checkfirst=True)
    SOURCE.drop(op.get_bind(), checkfirst=True)
