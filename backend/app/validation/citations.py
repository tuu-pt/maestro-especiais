"""Citations written in the text of the pieces (REF-01, REF-02, REF-03; Phase 5).

Diplomas ("Decreto-Lei n.º 96/2017", "Portaria n.º 949-A/2006"), standards ("NP EN 60 529",
"EN60898") and the RTIEBT by name. Each one is looked up in the corpus by the same patterns the
corpus was seeded with (app/knowledge/regulations.CORPUS).
"""

import re
from dataclasses import dataclass

from app.ingest.detect import fold
from app.knowledge.regulations import CORPUS

_DIPLOMA = re.compile(
    r"\b(?:Decreto(?:\s+de)?[\s\-\u2010-\u2014]*Lei|DL|Portaria|Despacho(?:\s+Normativo)?|Lei"
    r"|Decreto Regulamentar)"
    r"\s*(?:n\.?\s*[º°o]?\s*)?\d+(?:-[A-Z])?/\d{2,4}",
    re.I,
)
_STANDARD = re.compile(r"\b(?:NP\s+)?(?:EN|IEC|CEI|HD|ISO)\s?\d{2,3}(?:\s?\d{3})?(?:-\d+)*\b")
_RTIEBT = re.compile(r"\bRTIEBT\b", re.I)
_INCOMPLETE = re.compile(
    r"\b(?:sec[çc](?:[ãa]o|[õo]es)|artigos?)\s+d[aeo]s?\s+(?:RTIEBT|Regras\s+T[ée]cnicas)", re.I
)


@dataclass(frozen=True)
class Cited:
    text: str
    start: int
    code: str | None  # the corpus entry it matches, if any


def corpus_code(text: str) -> str | None:
    folded = fold(" ".join(text.split()))
    return next((r.code for r in CORPUS if re.search(r.pattern, folded)), None)


def find(text: str) -> list[Cited]:
    found: list[Cited] = []
    taken: list[tuple[int, int]] = []
    for pattern in (_DIPLOMA, _STANDARD, _RTIEBT):
        for m in pattern.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append(Cited(m.group(0), m.start(), corpus_code(m.group(0))))
    return sorted(found, key=lambda c: c.start)


def incomplete(text: str) -> list[re.Match[str]]:
    """ "segundo a secção das RTIEBT": a section of the RTIEBT without its number (C11)."""
    return list(_INCOMPLETE.finditer(text))
