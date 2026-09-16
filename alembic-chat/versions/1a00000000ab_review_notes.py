"""The coder's own words under a coded line (R-0270): the review_notes table,
which the first revision left out.

Revision ID: 1a00000000ab
Revises: 1a00000000aa
"""

from alembic import op
import sqlalchemy as sa

revision = '1a00000000ab'
down_revision = '1a00000000aa'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('review_notes',
    sa.Column('coding_id', sa.Integer(), nullable=False),
    sa.Column('statement_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('turn_id', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['coding_id'], ['review_codings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('review_notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_review_notes_coding_id'), ['coding_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_review_notes_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_review_notes_statement_id'), ['statement_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_review_notes_turn_id'), ['turn_id'], unique=False)


def downgrade():
    op.drop_table('review_notes')
