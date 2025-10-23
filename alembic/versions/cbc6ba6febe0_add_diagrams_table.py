"""Add diagrams table

Revision ID: cbc6ba6febe0
Revises: 
Create Date: 2021-10-30 21:52:50.207984

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'cbc6ba6febe0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if not 'diagrams' in tables:
        op.create_table(
            'diagrams',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),

            sa.Column('user_id', sa.Integer),
            sa.Column('data', sa.LargeBinary)
        )
        op.add_column('users', sa.Column('free_diagram_id', sa.Integer))


def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if 'diagrams' in tables:
        op.drop_table('diagrams')
        op.drop_column('users', 'free_diagram_id')
