"""Which fallback hops a model call took to be answered.

Revision ID: 1a00000000af
Revises: 1a00000000ae
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '1a00000000af'
down_revision = '1a00000000ae'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('model_calls', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fallback', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True))


def downgrade():
    with op.batch_alter_table('model_calls', schema=None) as batch_op:
        batch_op.drop_column('fallback')
