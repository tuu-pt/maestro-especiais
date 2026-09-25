"""Phase 3: reduced regulation corpus (references only, Annex D).

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "regulation_doc",
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=15), nullable=False),
        sa.Column("edition", sa.String(length=80), nullable=True),
        sa.Column("issuer", sa.String(length=80), nullable=True),
        sa.Column("scope", sa.String(length=300), nullable=False),
        sa.Column("specialties", JSONB, nullable=False),
        sa.Column("status", sa.String(length=15), nullable=True),
        sa.Column("citable", sa.Boolean(), nullable=False),
        sa.Column("copyrighted", sa.Boolean(), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("found_in", JSONB, nullable=False),
        sa.Column("found_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IS NULL OR status IN ('in_force', 'revoked', 'reference_only')",
            name="ck_regulation_doc_status",
        ),
        sa.CheckConstraint(
            "review_status IN ('proposed', 'confirmed', 'rejected')",
            name="ck_regulation_doc_review_status",
        ),
        sa.CheckConstraint(
            "kind IN ('diploma', 'guia', 'especificacao', 'norma')", name="ck_regulation_doc_kind"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("regulation_doc")
