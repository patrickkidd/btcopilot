"""add re-extraction cursor columns to discussion

Revision ID: c8f1a2d3e4b5
Revises: a57ced0bc0eb
Create Date: 2026-05-16

FD-319 re-extraction cursor. Both columns nullable; NULL = legacy behaviour
(extract from the start). Zero-risk backfill — existing rows stay NULL and
behave exactly as before until the first accepted re-extraction.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c8f1a2d3e4b5'
down_revision = 'a57ced0bc0eb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'discussions',
        sa.Column('extracted_through_order', sa.Integer(), nullable=True),
    )
    op.add_column(
        'discussions',
        sa.Column(
            'pending_extracted_through_order', sa.Integer(), nullable=True
        ),
    )


def downgrade():
    op.drop_column('discussions', 'pending_extracted_through_order')
    op.drop_column('discussions', 'extracted_through_order')
