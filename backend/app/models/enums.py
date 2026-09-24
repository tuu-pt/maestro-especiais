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


def one_of(
    column: str, values: tuple[str, ...], name: str, nullable: bool = False
) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    condition = f"{column} IN ({allowed})"
    if nullable:
        condition = f"{column} IS NULL OR {condition}"
    return CheckConstraint(condition, name=name)
