"""add_event_status_current_round

Revision ID: 6a6d86f5efbc
Revises: d4a954f65386
Create Date: 2026-01-28 09:08:00.472314

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a6d86f5efbc"
down_revision: Union[str, Sequence[str], None] = "d4a954f65386"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite: add non-null columns safely via batch mode.
    with op.batch_alter_table("event") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(), nullable=False, server_default="created")
        )
        batch_op.add_column(
            sa.Column("current_round", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("event") as batch_op:
        batch_op.drop_column("current_round")
        batch_op.drop_column("status")
