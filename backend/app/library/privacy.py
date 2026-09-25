"""Patterns of personal data in document text (SPEC 12). Used so that no block keeps them.

Only patterns: names are found through the known values of each project (ficha, cover and
signature), not here. A block paragraph with any of these left is not proposed as fixed or
parametric; archive text gets them masked.
"""

import re
from dataclasses import dataclass

MASK = "•••"
# a number is not part of a longer one or of a decimal ("0,123456789" is not a NIF)

_MONTHS = (
    "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
)
PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "nif": re.compile(r"(?<!\d)(?<!\d[.,])\d{9}(?!\d|[.,]\d)"),
    "cc": re.compile(
        r"\b\d{8}\s?\d\s?[A-Z]{2}\d\b|\bC\.?\s?C\.?\s*(?:n\.?º\s*)?:?\s*\d{6,9}\b", re.I
    ),
    "phone": re.compile(r"(?<!\d)(?<!\d[.,])(?:\+351\s?)?[29]\d{2}\s?\d{3}\s?\d{3}(?!\d|[.,]\d)"),
    "postal_code": re.compile(r"(?<!\d)(?<!\d[.,])\d{4}\s?[-\u2013]\s?\d{3}(?!\d|[.,]\d)"),
    "dgeg_oet": re.compile(r"\b(?:OET|DGEG|OE)\b\D{0,25}?\d{3,}", re.I),
    "address": re.compile(
        r"\b(?:Rua|Avenida|Av\.|Travessa|Largo|Praça|Estrada|Alameda|Urbanização)\s+"
        r"(?:d[aeo]s?\s+)?[A-ZÀ-Ý0-9][\w.º-]*",
    ),
    "date": re.compile(
        rf"\b\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}\b|\b(?:{_MONTHS})\s*(?:de\s*|/\s*|\|\s*)?\d{{4}}\b",
        re.I,
    ),
    "verification_code": re.compile(r"c[oó]digo de verifica[cç][aã]o\D{0,60}?[0-9a-f]{6,}", re.I),
}


@dataclass(frozen=True)
class Hit:
    kind: str
    start: int
    end: int
    text: str


def find(text: str) -> list[Hit]:
    hits = [
        Hit(kind, m.start(), m.end(), m.group(0))
        for kind, pattern in PATTERNS.items()
        for m in pattern.finditer(text)
    ]
    return sorted(hits, key=lambda h: (h.start, -h.end))


def mask(text: str) -> str:
    """Text with every hit replaced by •••."""
    out, last = [], 0
    for hit in find(text):
        if hit.start < last:
            continue
        out.append(text[last : hit.start])
        out.append(MASK)
        last = hit.end
    out.append(text[last:])
    return "".join(out)
