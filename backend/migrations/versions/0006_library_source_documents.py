"""Phase 3: reference MDJ/CTE split into sections, with their original OOXML.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _entity() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
    ]  # fmt: skip


def upgrade() -> None:
    op.create_table(
        "source_document",
        sa.Column("project_code", sa.String(length=32), nullable=False),
        sa.Column("doc_type", sa.String(length=3), nullable=False),
        sa.Column("specialty", sa.String(length=20), nullable=False),
        sa.Column("file", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("package_key", sa.String(length=200), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_entity(),
        sa.CheckConstraint("doc_type IN ('MDJ', 'CTE')", name="ck_source_document_doc_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_table(
        "source_section",
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("ooxml", sa.Text(), nullable=False),
        sa.Column("rels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_entity(),
        sa.CheckConstraint(
            "kind IN ('cover', 'index', 'block', 'signature')", name="ck_source_section_kind"
        ),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_document_id", "order", name="uq_source_section_order"),
    )
    op.create_index(
        "ix_source_section_source_document_id", "source_section", ["source_document_id"]
    )


def downgrade() -> None:
    op.drop_table("source_section")
    op.drop_table("source_document")
