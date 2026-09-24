"""What a reader returns: candidate values and circuits, each with its origin (SPEC P3)."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class Candidate:
    key: str
    value: Any
    source_ref: str  # e.g. "Ficha Eletrotecnica!P29" or "Tabela!linha 4"


@dataclass
class CircuitRow:
    row_index: int
    source_ref: str
    section: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadResult:
    source_type: str  # FichaValue.source_type
    template_version: str | None = None
    values: list[Candidate] = field(default_factory=list)
    circuits: list[CircuitRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # for people, never with personal values


def to_number(value: Any) -> Decimal | None:
    """Numbers as written in Portuguese sheets ("34,5", "1 250,00") or as floats."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def json_number(number: Decimal) -> int | float:
    """Decimal → JSON number, keeping integers as integers."""
    return int(number) if number == number.to_integral_value() else float(number)
