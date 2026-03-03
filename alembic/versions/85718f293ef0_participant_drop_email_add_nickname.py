"""participant: drop email add nickname

Revision ID: 85718f293ef0
Revises: 790c2abd3743
Create Date: 2026-02-21 12:42:08.593824

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "85718f293ef0"
down_revision: Union[str, Sequence[str], None] = "790c2abd3743"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    with op.batch_alter_table("participant") as batch:
        batch.add_column(sa.Column("nickname", sa.String(), nullable=True))
        batch.drop_column("email")


def downgrade():
    with op.batch_alter_table("participant") as batch:
        batch.add_column(sa.Column("email", sa.String(), nullable=True))
        batch.drop_column("nickname")
