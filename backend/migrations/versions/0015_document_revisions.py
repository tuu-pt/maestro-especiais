"""Phase 6: the técnico responsável, approval and revisions of a document.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document", sa.Column("revision", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("document", sa.Column("approved_by", sa.String(length=64), nullable=True))
    op.add_column("document", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document", sa.Column("header_date", sa.String(length=30), nullable=True))
    # the técnico responsável is who confirmed the ficha-base, not who assembled the document
    op.execute(
        "UPDATE document SET responsible_user_id = r.confirmed_by FROM ficha_revision r "
        "WHERE r.id = document.ficha_revision_id AND r.confirmed_by IS NOT NULL "
        "AND document.origin = 'assembled'"
    )
    op.create_table(
        "document_revision",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ficha_revision_id", sa.UUID(), nullable=True),
        sa.Column("header_date", sa.String(length=30), nullable=True),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reopened_by", sa.String(length=64), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ficha_revision_id"], ["ficha_revision.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "number", name="uq_document_revision"),
    )


def downgrade() -> None:
    op.drop_table("document_revision")
    for column in ("header_date", "approved_at", "approved_by", "revision"):
        op.drop_column("document", column)
