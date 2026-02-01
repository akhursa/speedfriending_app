"""add_event_phase_fields

Revision ID: 7d29d2021bc3
Revises: 0480482cf295
Create Date: 2026-02-01 10:39:20.464514

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d29d2021bc3'
down_revision: Union[str, Sequence[str], None] = '0480482cf295'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa

def upgrade():
    with op.batch_alter_table("event") as batch_op:
        batch_op.add_column(sa.Column("phase", sa.String(), nullable=False, server_default="lobby"))
        batch_op.add_column(sa.Column("phase_ends_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("event") as batch_op:
        batch_op.drop_column("phase_ends_at")
        batch_op.drop_column("phase")

