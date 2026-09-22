"""One row per model call: tokens, cost, time and tool calls, so cost per user
can be read at call granularity.

Revision ID: 1a00000000ad
Revises: 1a00000000ac
"""

from alembic import op
import sqlalchemy as sa

revision = '1a00000000ad'
down_revision = '1a00000000ac'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('model_calls',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('diagram_id', sa.Integer(), nullable=False),
    sa.Column('turn_id', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=64), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_creation_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_read_tokens', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('tool_calls', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['diagram_id'], ['diagrams.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('model_calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_model_calls_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_model_calls_turn_id'), ['turn_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_model_calls_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('model_calls', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_model_calls_user_id'))
        batch_op.drop_index(batch_op.f('ix_model_calls_turn_id'))
        batch_op.drop_index(batch_op.f('ix_model_calls_id'))
    op.drop_table('model_calls')
