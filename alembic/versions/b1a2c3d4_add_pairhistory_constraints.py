"""add pairhistory constraints and created_at

Revision ID: b1a2c3d4
Revises: 
Create Date: 2026-02-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1a2c3d4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # add created_at column (nullable)
    op.add_column('pairhistory', sa.Column('created_at', sa.DateTime(), nullable=True))
    # create unique constraint on (event_id,a_id,b_id)
    op.create_unique_constraint('uq_pairhistory_event_a_b', 'pairhistory', ['event_id', 'a_id', 'b_id'])
    # create index
    op.create_index('ix_pairhistory_event_a', 'pairhistory', ['event_id', 'a_id'])


def downgrade():
    op.drop_index('ix_pairhistory_event_a', table_name='pairhistory')
    op.drop_constraint('uq_pairhistory_event_a_b', 'pairhistory', type_='unique')
    op.drop_column('pairhistory', 'created_at')
