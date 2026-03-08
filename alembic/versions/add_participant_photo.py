"""Add participant photo fields

Revision ID: add_participant_photo
Revises:
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = "add_participant_photo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "participant", sa.Column("photo_filename", sa.String(), nullable=True)
    )
    op.add_column(
        "participant", sa.Column("photo_uploaded_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("participant", "photo_uploaded_at")
    op.drop_column("participant", "photo_filename")
