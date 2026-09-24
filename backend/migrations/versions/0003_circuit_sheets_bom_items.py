"""Phase 2: 09-Folhas (circuit_sheet), MQT/LPU lines (bom_item) and conflicts on circuit fields.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _entity() -> list[Any]:
    return [
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
        sa.PrimaryKeyConstraint("id"),
    ]


def _revision_and_file() -> list[Any]:
    return [
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("source_file_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["revision_id"], ["ficha_revision.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["project_file.id"], ondelete="SET NULL"),
    ]


def _link() -> list[Any]:
    return [
        sa.Column("link_status", sa.String(length=10), nullable=False),
        sa.Column("linked_by", sa.String(length=64), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
    ]


LINK_CHECK = "link_status IN ('rule', 'manual', 'unlinked')"


def upgrade() -> None:
    op.add_column("circuit", sa.Column("section_mm2", sa.Numeric(8, 2), nullable=True))

    op.alter_column("ficha_conflict", "value_id", nullable=True)
    op.add_column("ficha_conflict", sa.Column("circuit_id", sa.UUID(), nullable=True))
    op.add_column("ficha_conflict", sa.Column("field", sa.String(length=40), nullable=True))
    op.create_foreign_key(
        "ficha_conflict_circuit_id_fkey",
        "ficha_conflict",
        "circuit",
        ["circuit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_ficha_conflict_target",
        "ficha_conflict",
        "(value_id IS NOT NULL) <> (circuit_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_ficha_conflict_field", "ficha_conflict", "circuit_id IS NULL OR field IS NOT NULL"
    )
    op.create_index("ix_ficha_conflict_circuit_id", "ficha_conflict", ["circuit_id"])

    op.create_table(
        "circuit_sheet",
        *_revision_and_file(),
        sa.Column("origin_hint", sa.String(length=80), nullable=True),
        sa.Column("destination_hint", sa.String(length=80), nullable=True),
        sa.Column("template", sa.String(length=40), nullable=False),
        sa.Column("values", JSONB, nullable=False),
        sa.Column("circuit_ids", JSONB, nullable=False),
        *_link(),
        *_entity(),
        sa.CheckConstraint(LINK_CHECK, name="ck_circuit_sheet_link_status"),
    )
    op.create_index("ix_circuit_sheet_revision_id", "circuit_sheet", ["revision_id"])

    op.create_table(
        "bom_item",
        *_revision_and_file(),
        sa.Column("variant", sa.String(length=3), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("source_ref", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_code", sa.String(length=30), nullable=True),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("designation", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("total", sa.Numeric(16, 2), nullable=True),
        sa.Column("chapter_total", sa.Numeric(16, 2), nullable=True),
        sa.Column("link_key", sa.String(length=80), nullable=True),
        sa.Column("link_rule", sa.String(length=40), nullable=True),
        *_link(),
        *_entity(),
        sa.CheckConstraint("variant IN ('mqt', 'lpu')", name="ck_bom_item_variant"),
        sa.CheckConstraint(
            "kind IN ('chapter', 'subchapter', 'article', 'description', 'note', 'total')",
            name="ck_bom_item_kind",
        ),
        sa.CheckConstraint(LINK_CHECK, name="ck_bom_item_link_status"),
    )
    op.create_index("ix_bom_item_revision_id", "bom_item", ["revision_id"])


def downgrade() -> None:
    op.drop_table("bom_item")
    op.drop_table("circuit_sheet")
    op.drop_index("ix_ficha_conflict_circuit_id", table_name="ficha_conflict")
    op.drop_constraint("ck_ficha_conflict_field", "ficha_conflict", type_="check")
    op.drop_constraint("ck_ficha_conflict_target", "ficha_conflict", type_="check")
    op.drop_constraint("ficha_conflict_circuit_id_fkey", "ficha_conflict", type_="foreignkey")
    op.drop_column("ficha_conflict", "field")
    op.drop_column("ficha_conflict", "circuit_id")
    op.execute("DELETE FROM ficha_conflict WHERE value_id IS NULL")
    op.alter_column("ficha_conflict", "value_id", nullable=False)
    op.drop_column("circuit", "section_mm2")
