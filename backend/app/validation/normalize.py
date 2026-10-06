"""Values as the rules compare them: numbers as numbers, text folded (Phase 5).

Nothing is computed: "34,5" and "34.5" are the same number; "Rua  da Sé," and "rua da se" are
the same text. Anything else stays different.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingest.detect import fold

_NUMBER = re.compile(r"^[+-]?\d{1,3}(?:[ .]\d{3})*(?:,\d+)?$|^[+-]?\d+(?:[.,]\d+)?$")


def number(value: Any) -> float | None:
    """A number written the Portuguese way ("34,5", "1.234,5") or the English way ("34.5")."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().replace("\u00a0", " ")
    if not _NUMBER.match(text):
        return None
    if "," in text:
        text = text.replace(".", "").replace(" ", "").replace(",", ".")
    elif text.count(".") > 1 or re.match(r"^\d{1,3}(?:[ .]\d{3})+$", text):
        text = text.replace(".", "").replace(" ", "")  # thousands separators only
    try:
        return float(Decimal(text))
    except InvalidOperation:
        return None


MONTHS = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro")  # fmt: skip
_MONTH_YEAR = re.compile(rf"^({'|'.join(MONTHS)})\s*(?:de\s+|/\s*)?(\d{{4}})$")
_NUMERIC_MONTH_YEAR = re.compile(r"^(\d{1,2})\s*[/.-]\s*(\d{4}|\d{2})$")


def month_year(value: Any) -> str | None:
    """«JUNHO 2026», «junho de 2026», «06/2026» or «06/26» as an ISO month (2026-06)."""
    folded = text(value)
    m = _MONTH_YEAR.match(folded)
    if m:
        return f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}"
    m = _NUMERIC_MONTH_YEAR.match(folded)
    if m and 1 <= int(m.group(1)) <= 12:
        year = m.group(2) if len(m.group(2)) == 4 else f"20{m.group(2)}"
        return f"{year}-{int(m.group(1)):02d}"
    return None


def shown_date(iso: str | None) -> str:
    """2026-06 → «junho de 2026»; 2026-10-06 → «06/10/2026»."""
    if not iso:
        return "(sem data)"
    parts = iso.split("-")
    if len(parts) == 2:
        month = MONTHS[int(parts[1]) - 1].replace("marco", "março")
        return f"{month} de {parts[0]}"
    return "/".join(reversed(parts))


def text(value: Any) -> str:
    """Folded text: no accents, lower case, single spaces, no punctuation at the ends."""
    folded = fold(str(value or ""))
    folded = re.sub(r"[\s\u00a0]+", " ", folded)
    return folded.strip(" .,;:-\u2013\u2014").strip()


def same(a: Any, b: Any) -> bool:
    """Equal as numbers when both are numbers, otherwise equal as folded text."""
    na, nb = number(a), number(b)
    if na is not None and nb is not None:
        return abs(na - nb) < 1e-9
    if isinstance(a, list) or isinstance(b, list):
        return sorted(map(text, a if isinstance(a, list) else [a])) == sorted(
            map(text, b if isinstance(b, list) else [b])
        )
    return text(a) == text(b)


def shown_number(value: float) -> str:
    """How a number is shown in the evidence: Portuguese decimal comma, no trailing zeros."""
    out = f"{value:.4f}".rstrip("0").rstrip(".")
    return out.replace(".", ",")
