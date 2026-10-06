"""Phase 7: equipment library (equipment, datasheets, parameters, requirements, project slots).

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column("identity", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("manufacturer", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("code", sa.String(length=10), nullable=True),
        sa.Column("specialties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("or_equivalent", sa.Boolean(), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("image", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            "status IN ('proposed', 'approved', 'rejected')", name="ck_equipment_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity"),
    )
    op.create_table(
        "datasheet",
        sa.Column("equipment_id", sa.UUID(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("issue_date_text", sa.String(length=60), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.CheckConstraint("status IN ('current', 'outdated')", name="ck_datasheet_status"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id", "sha256", name="uq_datasheet_sha256"),
    )
    op.create_table(
        "equipment_requirement",
        sa.Column("doc_type", sa.String(length=3), nullable=False),
        sa.Column("block_key", sa.String(length=200), nullable=False),
        sa.Column("equipment_id", sa.UUID(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("param_name", sa.String(length=40), nullable=False),
        sa.Column("operator", sa.String(length=8), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "operator IN ('>=', '<=', '=', '>=class', 'info')",
            name="ck_equipment_requirement_operator",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected')", name="ck_equipment_requirement_status"
        ),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "equipment_param",
        sa.Column("equipment_id", sa.UUID(), nullable=False),
        sa.Column("datasheet_id", sa.UUID(), nullable=True),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("origin IN ('cte', 'datasheet')", name="ck_equipment_param_origin"),
        sa.CheckConstraint(
            "review_status IN ('extracted', 'reviewed')", name="ck_equipment_param_review"
        ),
        sa.ForeignKeyConstraint(["datasheet_id"], ["datasheet.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "project_equipment",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("entry", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("block_key", sa.String(length=200), nullable=False),
        sa.Column("default_equipment_id", sa.UUID(), nullable=True),
        sa.Column("equipment_id", sa.UUID(), nullable=True),
        sa.Column("or_equivalent", sa.Boolean(), nullable=False),
        sa.Column("ficha_key", sa.String(length=80), nullable=True),
        sa.Column("chosen_by", sa.String(length=64), nullable=True),
        sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["default_equipment_id"], ["equipment.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["section.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "entry", "slot", name="uq_project_equipment_slot"),
    )
    op.create_index("ix_equipment_param_equipment_id", "equipment_param", ["equipment_id"])
    op.create_index("ix_equipment_requirement_block_key", "equipment_requirement", ["block_key"])
    op.create_index("ix_project_equipment_project_id", "project_equipment", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_equipment_project_id", table_name="project_equipment")
    op.drop_index("ix_equipment_requirement_block_key", table_name="equipment_requirement")
    op.drop_index("ix_equipment_param_equipment_id", table_name="equipment_param")
    op.drop_table("project_equipment")
    op.drop_table("equipment_param")
    op.drop_table("equipment_requirement")
    op.drop_table("datasheet")
    op.drop_table("equipment")
