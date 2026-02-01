"""add_pairhistory

Revision ID: 0480482cf295
Revises: 6a6d86f5efbc
Create Date: 2026-02-01 10:15:44.035625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0480482cf295'
down_revision: Union[str, Sequence[str], None] = '6a6d86f5efbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pairhistory",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("a_id", sa.Integer(), nullable=False),
        sa.Column("b_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], name="fk_pairhistory_event_id"),
        sa.ForeignKeyConstraint(["a_id"], ["participant.id"], name="fk_pairhistory_a_id"),
        sa.ForeignKeyConstraint(["b_id"], ["participant.id"], name="fk_pairhistory_b_id"),
        sa.UniqueConstraint("event_id", "a_id", "b_id", "round_number", name="uq_pairhistory_event_a_b_round"),
    )
    op.create_index("ix_pairhistory_event_id", "pairhistory", ["event_id"], unique=False)
    op.create_index("ix_pairhistory_round_number", "pairhistory", ["round_number"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_pairhistory_round_number", table_name="pairhistory")
    op.drop_index("ix_pairhistory_event_id", table_name="pairhistory")
    op.drop_table("pairhistory")
