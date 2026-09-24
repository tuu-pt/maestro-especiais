"""Board names written in different ways in different sources (SPEC 8.2, Phase 2).

The Tabela de Cálculo writes "Q.P.BIB.INFANT." where a 09-Folha file is called "QEG-QP.BIB.INF",
"Q.P.ATRIO" where the file says "ATRIO", and R1 uses both "QE" and "Q.E.G." for the same board.
Names are compared by their core: upper case, no accents, no separators, without the board-type
prefix (Q, QP), with the supply entry and the main board under one name each. A match is exact,
or else a unique prefix; anything ambiguous is left for a person to associate.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

_ENTRY = {"PORT", "PORTINHOLA", "ARM", "ARMARIO", "CP", "CAIXAPORTINHOLA"}
_MAIN = {"QE", "QEG", "QGBT", "QG"}
_SHEET_PREFIX = re.compile(r"^\s*(?:\d+\s*-\s*)?folha\s+de\s+c[aá]lculo\s*", re.I)


def canonical(name: str) -> str:
    """Upper case, no accents, only letters and digits: "Q.P.BIB.INFANT." → "QPBIBINFANT"."""
    plain = unicodedata.normalize("NFKD", name)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^0-9A-Z]", "", plain.upper())


def core(name: str) -> str:
    """The part of a board name that identifies it: "Q.P.ATRIO" and "ATRIO" → "ATRIO"."""
    text = canonical(re.sub(r"(?i)^\s*quadro\s+", "", name))
    if text in _ENTRY:
        return "PORTINHOLA"
    if text in _MAIN:
        return "QEG"
    for prefix in ("QP", "Q"):
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix) :]
    return text


def same_board(a: str, b: str) -> bool:
    return core(a) == core(b)


def parse_sheet_name(filename: str) -> tuple[str, str] | None:
    """(origin, destination) in the name of a 09-Folha file: "…Cálculo QUPS-QUPS.P-1.xls".

    The two boards are split at the first hyphen followed by a letter ("P-1" stays whole).
    """
    stem = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", filename.rsplit("/", 1)[-1])
    stem = _SHEET_PREFIX.sub("", stem).strip()
    match = re.search(r"-(?=[A-Za-zÀ-ÿ])", stem)
    if not match:
        return None
    origin, destination = stem[: match.start()].strip(), stem[match.end() :].strip()
    return (origin, destination) if origin and destination else None


@dataclass(frozen=True)
class Named:
    """A circuit as the matcher sees it."""

    id: object
    origin: str
    destination: str


def _score(hint: str, name: str) -> int:
    """2 = same core, 1 = one core is a prefix of the other, 0 = different."""
    a, b = core(hint), core(name)
    if not a or not b:
        return 0
    if a == b:
        return 2
    return 1 if a.startswith(b) or b.startswith(a) else 0


def match_circuits(origin: str, destination: str, circuits: Sequence[Named]) -> list[object]:
    """Ids of the circuits that best match (origin, destination); more than one is ambiguous."""
    scored = []
    for c in circuits:
        o, d = _score(origin, c.origin), _score(destination, c.destination)
        if o and d:
            scored.append((o + d, c.id))
    if not scored:
        return []
    best = max(s for s, _ in scored)
    return [cid for s, cid in scored if s == best]
