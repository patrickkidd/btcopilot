"""A real turn can be run again on several shadow models, one row per real turn
and model [R-0596].

Revision ID: 1b00000000bf
Revises: 1b00000000be
"""

from alembic import op

revision = "1b00000000bf"
down_revision = "1b00000000be"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("shadow_turns", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_shadow_turns_turn_id"))
        batch_op.create_unique_constraint(
            "uq_shadow_turns_turn_model", ["turn_id", "model"]
        )


def downgrade():
    raise NotImplementedError("roll forward instead")
