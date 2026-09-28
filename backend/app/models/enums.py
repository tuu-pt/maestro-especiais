"""Allowed values of the enumerated columns (stored as text with CHECK constraints)."""

from sqlalchemy import CheckConstraint

PROJECT_PHASES = ("licenciamento", "execucao")
PROJECT_STATUSES = ("active", "archived")
FILE_KINDS = (
    "ficha_eletrotecnica",
    "calc_summary",
    "calc_circuit",
    "mqt",
    "lpu",
    "drawing_pdf",
    "drawing_dwg",
    "archive_docx",
    "mdj_docx",
    "cte_docx",
    "identificacao_docx",
    "termo_docx",
    "other",
)
INGEST_STATUSES = ("pending", "running", "done", "failed", "skipped")
REVISION_STATUSES = ("draft", "confirmed", "superseded")
VALUE_STATUSES = ("confirmed", "conflict", "pending")
SOURCE_TYPES = ("ficha_eletrotecnica", "calc", "mqt", "drawing", "manual")
ACTOR_TYPES = ("agent", "user", "system")
PROTECTION_TYPES = ("D", "F")
POLE_TYPES = ("MON", "MUL")
INSTALLATIONS = ("TUB", "EST", "ENT", "AR")
CONDUCTORS = ("Cu", "Al")
LINK_STATUSES = ("rule", "manual", "unlinked")
REVIEW_STATUSES = ("proposed", "approved", "rejected")  # what a curator reviews
LIBRARY_DOC_TYPES = ("MDJ", "CTE")
SECTION_KINDS = ("cover", "index", "block", "signature")
BLOCK_MODES = ("fixed", "parametric", "adaptive")
REGULATION_STATUSES = ("in_force", "revoked", "reference_only")  # legal status (SPEC 7.5)
REGULATION_REVIEW = ("proposed", "confirmed", "rejected")
REGULATION_KINDS = ("diploma", "guia", "especificacao", "norma")
DOCUMENT_TYPES = ("MDJ", "CTE", "FICHA_ELE", "IDENTIFICACAO", "TERMO")
DOCUMENT_STATUSES = ("draft", "in_review", "approved")
DOCUMENT_ORIGINS = ("assembled", "existing")
SECTION_STATUSES = ("todo", "generated", "reviewed", "alert")
VERSION_STATUSES = ("current", "proposed", "rejected", "superseded")
LLM_CALL_STATUSES = ("ok", "invalid", "failed", "blocked", "refused")
BOM_VARIANTS = ("mqt", "lpu")
BOM_KINDS = ("chapter", "subchapter", "article", "description", "note", "total")
ISSUE_SEVERITIES = ("critical", "warning", "info")
ISSUE_STATUSES = ("open", "fixed", "ignored")
RUN_STATUSES = ("queued", "running", "done", "failed")
RUN_TRIGGERS = ("full", "changed")


def one_of(
    column: str, values: tuple[str, ...], name: str, nullable: bool = False
) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    condition = f"{column} IN ({allowed})"
    if nullable:
        condition = f"{column} IS NULL OR {condition}"
    return CheckConstraint(condition, name=name)
