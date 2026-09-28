"""Phase 5: validation runs, their issues and the facts read from each piece.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "piece_facts",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("piece_ref", sa.String(length=60), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extractor_version", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "piece_ref", name="uq_piece_facts_ref"),
    )
    op.create_table(
        "validation_run",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("ficha_revision_id", sa.UUID(), nullable=True),
        sa.Column("document_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pieces", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trigger", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("totals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "status IN ('queued', 'running', 'done', 'failed')", name="ck_validation_run_status"
        ),
        sa.CheckConstraint("trigger IN ('full', 'changed')", name="ck_validation_run_trigger"),
        sa.ForeignKeyConstraint(["ficha_revision_id"], ["ficha_revision.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "validation_issue",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(length=10), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("message_pt", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("likely_reading", sa.Text(), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("new", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("ignored_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            "severity IN ('critical', 'warning', 'info')", name="ck_validation_issue_severity"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'fixed', 'ignored')", name="ck_validation_issue_status"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["validation_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_issue_run", "validation_issue", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_validation_issue_run", table_name="validation_issue")
    op.drop_table("validation_issue")
    op.drop_table("validation_run")
    op.drop_table("piece_facts")
