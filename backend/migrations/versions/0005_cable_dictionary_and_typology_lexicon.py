"""Phase 3: cable dictionary (designations, occurrences, proposed equivalences) and lexicon.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cable_designation",
        sa.Column("canonical", sa.String(length=60), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kind", sa.String(length=5), nullable=False),
        sa.Column("flexible", sa.Boolean(), nullable=True),
        sa.Column("fire_class_default", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name="ck_cable_designation_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical"),
    )
    op.create_table(
        "typology",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name="ck_typology_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "cable_equivalence",
        sa.Column("a_id", sa.UUID(), nullable=False),
        sa.Column("b_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name="ck_cable_equivalence_status"
        ),
        sa.ForeignKeyConstraint(["a_id"], ["cable_designation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["b_id"], ["cable_designation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("a_id", "b_id", name="uq_cable_equivalence_pair"),
    )
    op.create_table(
        "cable_occurrence",
        sa.Column("designation_id", sa.UUID(), nullable=False),
        sa.Column("project_code", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("locator", sa.String(length=120), nullable=False),
        sa.Column("raw_text", sa.String(length=160), nullable=False),
        sa.Column("geometry", sa.String(length=30), nullable=True),
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
        sa.ForeignKeyConstraint(["designation_id"], ["cable_designation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "typology_term",
        sa.Column("typology_id", sa.UUID(), nullable=False),
        sa.Column("term", sa.String(length=80), nullable=False),
        sa.Column("relation", sa.String(length=20), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name="ck_typology_term_status"
        ),
        sa.ForeignKeyConstraint(["typology_id"], ["typology.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("typology_id", "term", name="uq_typology_term"),
    )
    op.create_index("ix_cable_occurrence_designation_id", "cable_occurrence", ["designation_id"])


def downgrade() -> None:
    op.drop_table("typology_term")
    op.drop_table("cable_occurrence")
    op.drop_table("cable_equivalence")
    op.drop_table("typology")
    op.drop_table("cable_designation")
