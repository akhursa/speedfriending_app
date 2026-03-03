"""add participant.nickname

Revision ID: 790c2abd3743
Revises: 90ab5f2b2007
Create Date: 2026-02-21 12:07:54.999730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '790c2abd3743'
down_revision: Union[str, Sequence[str], None] = '90ab5f2b2007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
