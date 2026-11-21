"""The ballot by pairing: each review item keeps the model's one-line reason
for its pairing and how sure it was, the cut keeps which model and prompt
built its pairings and whether the job is building, built or failed; a model
call for pairings is its own purpose, and a failed fixed check its own
observation kind.

Revision ID: 1b00000000c7
Revises: 1b00000000c6
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "1b00000000c7"
down_revision = "1b00000000c6"
branch_labels = None
depends_on = None

CONFIDENCE = sa.Enum("sure", "likely", "unsure", name="pairingconfidence")


def upgrade():
    bind = op.get_bind()
    CONFIDENCE.create(bind, checkfirst=True)
    op.add_column("review_items", sa.Column("pairing_reason", sa.Text(), nullable=True))
    op.add_column(
        "review_items", sa.Column("pairing_confidence", CONFIDENCE, nullable=True)
    )
    op.add_column(
        "review_cuts",
        sa.Column(
            "pairing_agent",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE purpose ADD VALUE IF NOT EXISTS 'pairing'")
            op.execute(
                "ALTER TYPE observationkind ADD VALUE IF NOT EXISTS 'pairing_check'"
            )


def downgrade():
    op.drop_column("review_cuts", "pairing_agent")
    op.drop_column("review_items", "pairing_confidence")
    op.drop_column("review_items", "pairing_reason")
    CONFIDENCE.drop(op.get_bind(), checkfirst=True)
    # Postgres cannot drop an enum label; both stay, unused.
