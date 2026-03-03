"""merge heads

Revision ID: 90ab5f2b2007
Revises: 7d29d2021bc3, b1a2c3d4
Create Date: 2026-02-21 12:07:03.981815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90ab5f2b2007'
down_revision: Union[str, Sequence[str], None] = ('7d29d2021bc3', 'b1a2c3d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#def upgrade() -> None:
#    """Upgrade schema."""
#    pass


#def downgrade() -> None:
#    """Downgrade schema."""
#    pass

def upgrade():
    op.add_column("participant", sa.Column("nickname", sa.String(), nullable=True))

def downgrade():
    op.drop_column("participant", "nickname")

    