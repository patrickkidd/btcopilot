"""add_reconciliation_notes

Revision ID: a1b2c3d4e5f6
Revises: fea616e0fe7d
Create Date: 2026-01-08

"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "fea616e0fe7d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reconciliation_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("statement_id", sa.Integer(), sa.ForeignKey("statements.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("resolved", sa.Boolean(), default=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )


def downgrade():
    op.drop_table("reconciliation_notes")
