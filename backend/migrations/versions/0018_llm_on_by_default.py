"""The LLM on by default for new projects (D5, user's decision of 8 Oct 2026).

Existing projects keep their value: an admin may have turned it off on purpose.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("project", "llm_allowed", server_default="true")


def downgrade() -> None:
    op.alter_column("project", "llm_allowed", server_default="false")
