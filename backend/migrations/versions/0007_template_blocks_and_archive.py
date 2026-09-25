"""Phase 3: proposed template blocks and the archive of the reference documents.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _entity() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
    ]  # fmt: skip


def _review() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "template_block",
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=3), nullable=False),
        sa.Column("specialty", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("activation_rule", sa.Text(), nullable=True),
        sa.Column("activation_ast", JSONB, nullable=True),
        sa.Column("body_template", JSONB, nullable=False),
        sa.Column("locked_ooxml", sa.Text(), nullable=True),
        sa.Column("ooxml_rels", JSONB, nullable=False),
        sa.Column("required_keys", JSONB, nullable=False),
        sa.Column("equipment_slots", JSONB, nullable=False),
        sa.Column("archive_refs", JSONB, nullable=False),
        sa.Column("projects", JSONB, nullable=False),
        sa.Column("source_refs", JSONB, nullable=False),
        sa.Column("notes", JSONB, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_review(),
        *_entity(),
        sa.CheckConstraint("doc_type IN ('MDJ', 'CTE')", name="ck_template_block_doc_type"),
        sa.CheckConstraint(
            "kind IN ('cover', 'index', 'block', 'signature')", name="ck_template_block_kind"
        ),
        sa.CheckConstraint(
            "mode IN ('fixed', 'parametric', 'adaptive')", name="ck_template_block_mode"
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name="ck_template_block_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "doc_type", "specialty", "key", "version", name="uq_template_block_key"
        ),
    )
    op.create_table(
        "archive_doc",
        sa.Column("project_code", sa.String(length=32), nullable=False),
        sa.Column("doc_type", sa.String(length=3), nullable=False),
        sa.Column("specialty", sa.String(length=20), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        *_entity(),
        sa.CheckConstraint("doc_type IN ('MDJ', 'CTE')", name="ck_archive_doc_doc_type"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "archive_chunk",
        sa.Column("archive_doc_id", sa.UUID(), nullable=False),
        sa.Column("block_key", sa.String(length=200), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_section_id", sa.UUID(), nullable=True),
        *_entity(),
        sa.ForeignKeyConstraint(["archive_doc_id"], ["archive_doc.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_section_id"], ["source_section.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_archive_chunk_archive_doc_id", "archive_chunk", ["archive_doc_id"])
    op.create_index("ix_archive_chunk_block_key", "archive_chunk", ["block_key"])


def downgrade() -> None:
    op.drop_table("archive_chunk")
    op.drop_table("archive_doc")
    op.drop_table("template_block")
