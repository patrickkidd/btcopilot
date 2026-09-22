"""Cache tokens on the meter: what a turn wrote to the prompt cache and what it
read back are priced apart from plain input.

Revision ID: 1a00000000ac
Revises: 1a00000000ab
"""

from alembic import op
import sqlalchemy as sa

revision = '1a00000000ac'
down_revision = '1a00000000ab'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('token_meters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cache_creation_tokens', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('cache_read_tokens', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('token_meters', schema=None) as batch_op:
        batch_op.drop_column('cache_read_tokens')
        batch_op.drop_column('cache_creation_tokens')
