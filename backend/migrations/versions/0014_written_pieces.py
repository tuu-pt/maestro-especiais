"""Phase 5: written pieces made by hand (MDJ, CTE, identification, term) to audit.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_BEFORE = (
    "ficha_eletrotecnica", "calc_summary", "calc_circuit", "mqt", "lpu", "drawing_pdf",
    "drawing_dwg", "archive_docx", "other",
)  # fmt: skip
KINDS = (*KINDS_BEFORE[:-1], "mdj_docx", "cte_docx", "identificacao_docx", "termo_docx", "other")


def _kinds(values: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint("ck_project_file_kind", "project_file", type_="check")
    op.create_check_constraint("ck_project_file_kind", "project_file", _kinds(KINDS))
    op.add_column(
        "document",
        sa.Column("origin", sa.String(length=10), server_default="assembled", nullable=False),
    )
    op.add_column("document", sa.Column("source_file_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "document_source_file_id_fkey", "document", "project_file", ["source_file_id"], ["id"],
        ondelete="SET NULL",
    )  # fmt: skip
    op.create_check_constraint(
        "ck_document_origin", "document", "origin IN ('assembled', 'existing')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_origin", "document", type_="check")
    op.drop_constraint("document_source_file_id_fkey", "document", type_="foreignkey")
    op.drop_column("document", "source_file_id")
    op.drop_column("document", "origin")
    op.execute("DELETE FROM project_file WHERE kind IN "
               "('mdj_docx', 'cte_docx', 'identificacao_docx', 'termo_docx')")  # fmt: skip
    op.drop_constraint("ck_project_file_kind", "project_file", type_="check")
    op.create_check_constraint("ck_project_file_kind", "project_file", _kinds(KINDS_BEFORE))
