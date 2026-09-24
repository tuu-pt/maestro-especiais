"""Audit events take the real time of each event (clock_timestamp), not the transaction start.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("audit_event", "at", server_default=sa.text("clock_timestamp()"))


def downgrade() -> None:
    op.alter_column("audit_event", "at", server_default=sa.text("now()"))
