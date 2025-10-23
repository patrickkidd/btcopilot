"""Add name column top Diagram

Revision ID: 7c9e805e2b21
Revises: cbc6ba6febe0
Create Date: 2022-01-02 22:22:58.884082

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '7c9e805e2b21'
down_revision = 'cbc6ba6febe0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    op.add_column('diagrams', sa.Column('name', sa.String))
    op.add_column('diagrams', sa.Column('alias', sa.String))
    op.add_column('diagrams', sa.Column('use_real_names', sa.Boolean))
    op.add_column('diagrams', sa.Column('require_password_for_real_names', sa.Boolean))

def downgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    op.drop_column('diagrams', 'name')
    op.drop_column('diagrams', 'alias')
    op.drop_column('diagrams', 'use_real_names')
    op.drop_column('diagrams', 'require_password_for_real_names')
