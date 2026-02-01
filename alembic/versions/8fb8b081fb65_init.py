"""init

Revision ID: 8fb8b081fb65
Revises:
Create Date: 2026-01-28 08:06:01.598813

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8fb8b081fb65"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # event
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("join_code", sa.String(), nullable=False),
        sa.Column(
            "timezone", sa.String(), nullable=False, server_default="Europe/Minsk"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("join_code", name="uq_event_join_code"),
    )
    op.create_index("ix_event_join_code", "event", ["join_code"], unique=True)

    # participant
    op.create_table(
        "participant",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name="fk_participant_event_id"
        ),
        sa.UniqueConstraint("event_id", "email", name="uq_participant_event_email"),
    )
    op.create_index(
        "ix_participant_event_id", "participant", ["event_id"], unique=False
    )
    op.create_index("ix_participant_email", "participant", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_participant_email", table_name="participant")
    op.drop_index("ix_participant_event_id", table_name="participant")
    op.drop_table("participant")

    op.drop_index("ix_event_join_code", table_name="event")
    op.drop_table("event")
