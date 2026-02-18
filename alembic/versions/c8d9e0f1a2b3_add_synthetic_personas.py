"""Add synthetic_personas table and discussions.synthetic_persona_id FK

Revision ID: c8d9e0f1a2b3
Revises: a1b2c3d4e5f6
Create Date: 2026-02-17 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c8d9e0f1a2b3"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "synthetic_personas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("background", sa.Text(), nullable=False),
        sa.Column("traits", sa.JSON(), nullable=False),
        sa.Column("attachment_style", sa.Text(), nullable=False),
        sa.Column("presenting_problem", sa.Text(), nullable=False),
        sa.Column("data_points", sa.JSON(), nullable=True),
        sa.Column("sex", sa.Text(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column(
        "discussions",
        sa.Column(
            "synthetic_persona_id",
            sa.Integer(),
            nullable=True,
            comment="FK to synthetic_personas for generated persona linkage",
        ),
    )
    op.create_index(
        op.f("ix_discussions_synthetic_persona_id"),
        "discussions",
        ["synthetic_persona_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_discussions_synthetic_persona_id"), table_name="discussions")
    op.drop_column("discussions", "synthetic_persona_id")
    op.drop_table("synthetic_personas")
