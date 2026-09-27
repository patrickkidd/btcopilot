"""The quality dashboard's recorded runs: one row per measured value of a run
kept in the repository. The table starts empty; every release loads it.

Revision ID: 1b00000000af
Revises: 1b00000000ae
"""

from alembic import op
import sqlalchemy as sa

revision = "1b00000000af"
down_revision = "1b00000000ae"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_runs",
        sa.Column("ran_at", sa.DateTime(), nullable=False),
        sa.Column("commit", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("eval_pass_rate", "extraction_f1", "coding_f1", name="qualitykind"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "ran_at", "commit", "metric", name="uq_quality_runs_run"),
    )
    with op.batch_alter_table("quality_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_quality_runs_id"), ["id"])


def downgrade():
    op.drop_table("quality_runs")
    sa.Enum(name="qualitykind").drop(op.get_bind(), checkfirst=True)
