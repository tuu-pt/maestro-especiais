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
