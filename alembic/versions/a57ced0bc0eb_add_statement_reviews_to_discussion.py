"""add statement_reviews to discussion

Revision ID: a57ced0bc0eb
Revises: b3c4d5e6f7a8
Create Date: 2026-04-27 22:06:06.937258

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a57ced0bc0eb'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('discussions', sa.Column('statement_reviews', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('discussions', 'statement_reviews')
