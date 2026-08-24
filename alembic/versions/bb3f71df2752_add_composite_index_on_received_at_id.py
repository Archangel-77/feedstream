"""add composite index on received_at and id

Revision ID: bb3f71df2752
Revises: a88a72ae9625
Create Date: 2026-08-24 09:46:40.606492

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb3f71df2752"
down_revision: str | Sequence[str] | None = "a88a72ae9625"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_events_received_at_id",
        "events",
        ["received_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_events_received_at_id", table_name="events")
