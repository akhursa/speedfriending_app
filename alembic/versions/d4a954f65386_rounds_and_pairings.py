"""rounds_and_pairings

Revision ID: d4a954f65386
Revises: 8fb8b081fb65
Create Date: 2026-01-28 08:21:50.452805

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4a954f65386"
down_revision: Union[str, Sequence[str], None] = "8fb8b081fb65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # round
    op.create_table(
        "round",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], name="fk_round_event_id"),
        sa.UniqueConstraint("event_id", "number", name="uq_round_event_number"),
    )
    op.create_index("ix_round_event_id", "round", ["event_id"], unique=False)
    op.create_index("ix_round_number", "round", ["number"], unique=False)

    # pairing
    op.create_table(
        "pairing",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("p1_id", sa.Integer(), nullable=False),
        sa.Column("p2_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="assigned"),
        sa.Column("met_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], name="fk_pairing_event_id"),
        sa.ForeignKeyConstraint(["p1_id"], ["participant.id"], name="fk_pairing_p1_id"),
        sa.ForeignKeyConstraint(["p2_id"], ["participant.id"], name="fk_pairing_p2_id"),
        sa.UniqueConstraint(
            "event_id", "round_number", "p1_id", name="uq_pairing_event_round_p1"
        ),
    )
    op.create_index("ix_pairing_event_id", "pairing", ["event_id"], unique=False)
    op.create_index(
        "ix_pairing_round_number", "pairing", ["round_number"], unique=False
    )

    # pair_history (история встреч для анти-повторов)
    op.create_table(
        "pairhistory",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("a_id", sa.Integer(), nullable=False),
        sa.Column("b_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name="fk_pairhistory_event_id"
        ),
        sa.ForeignKeyConstraint(
            ["a_id"], ["participant.id"], name="fk_pairhistory_a_id"
        ),
        sa.ForeignKeyConstraint(
            ["b_id"], ["participant.id"], name="fk_pairhistory_b_id"
        ),
        sa.UniqueConstraint(
            "event_id",
            "a_id",
            "b_id",
            "round_number",
            name="uq_pairhistory_event_a_b_round",
        ),
    )
    op.create_index(
        "ix_pairhistory_event_id", "pairhistory", ["event_id"], unique=False
    )
    op.create_index(
        "ix_pairhistory_round_number", "pairhistory", ["round_number"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_pairhistory_round_number", table_name="pairhistory")
    op.drop_index("ix_pairhistory_event_id", table_name="pairhistory")
    op.drop_table("pairhistory")

    op.drop_index("ix_pairing_round_number", table_name="pairing")
    op.drop_index("ix_pairing_event_id", table_name="pairing")
    op.drop_table("pairing")

    op.drop_index("ix_round_number", table_name="round")
    op.drop_index("ix_round_event_id", table_name="round")
    op.drop_table("round")
