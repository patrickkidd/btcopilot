"""One row per screen opened or named tap, so feature use per person over time
can be read in Grafana.

Revision ID: 1a00000000ae
Revises: 1a00000000ad
"""

from alembic import op
import sqlalchemy as sa

revision = '1a00000000ae'
down_revision = '1a00000000ad'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_events',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('diagram_id', sa.Integer(), nullable=True),
    sa.Column('screen', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('item_kind', sa.String(length=32), nullable=True),
    sa.Column('item_id', sa.String(length=64), nullable=True),
    sa.Column('client_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['diagram_id'], ['diagrams.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('product_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_product_events_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_product_events_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_product_events_user_id_created_at', ['user_id', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('product_events', schema=None) as batch_op:
        batch_op.drop_index('ix_product_events_user_id_created_at')
        batch_op.drop_index(batch_op.f('ix_product_events_user_id'))
        batch_op.drop_index(batch_op.f('ix_product_events_id'))
    op.drop_table('product_events')
