"""A pick keeps the two reply texts it judged, left and right as served, so a
replay or shadow row deleted later never loses what Patrick picked between
[R-0599]. Picks served before this revision take their texts from the rows
still there; one not yet picked whose reply is already gone can never be
shown again, so it goes.

Revision ID: 1b00000000be
Revises: 1b00000000bd
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "1b00000000be"
down_revision = "1b00000000bd"
branch_labels = None
depends_on = None

JSON = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
SIDES = ("left", "right")
PICKS = sa.table(
    "model_picks",
    sa.column("choice"),
    *(sa.column(f"{side}_ref", JSON) for side in SIDES),
    *(sa.column(f"{side}_text") for side in SIDES),
)
SOURCES = {
    "statement_id": sa.table("statements", sa.column("id"), sa.column("text")),
    "shadow_id": sa.table("shadow_turns", sa.column("id"), sa.column("text")),
}


def upgrade():
    with op.batch_alter_table("model_picks", schema=None) as batch_op:
        for side in SIDES:
            batch_op.add_column(sa.Column(f"{side}_text", sa.Text(), nullable=True))
    for side in SIDES:
        for key, source in SOURCES.items():
            ref = PICKS.c[f"{side}_ref"][key].as_integer()
            op.execute(
                PICKS.update()
                .where(ref.isnot(None))
                .values(
                    {
                        f"{side}_text": sa.select(source.c.text)
                        .where(source.c.id == ref)
                        .scalar_subquery()
                    }
                )
            )
    op.execute(
        PICKS.delete().where(
            PICKS.c.choice.is_(None),
            sa.or_(PICKS.c.left_text.is_(None), PICKS.c.right_text.is_(None)),
        )
    )
    with op.batch_alter_table("model_picks", schema=None) as batch_op:
        for side in SIDES:
            batch_op.alter_column(
                f"{side}_text", existing_type=sa.Text(), nullable=False
            )


def downgrade():
    with op.batch_alter_table("model_picks", schema=None) as batch_op:
        for side in SIDES:
            batch_op.drop_column(f"{side}_text")
