"""Rule-based links from MQT/LPU articles to ficha-base keys (SPEC 8.2, Phase 2: rules only).

Each rule is explicit and tested: boards by name, the portinhola, EV chargers, PV modules and
luminaires by their code (L1, L4.1, SNC…). An article no rule recognizes stays "unlinked" and is
shown for a person to link. Assisted linking with the LLM is future work (SPEC 8.2).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.ingest.detect import fold

_BOARD = re.compile(r"^Q[.\s]?[A-Z0-9À-Ý]")
# Luminaires by their code ("L4.1 - Luminária…", "SNC - Luminária…"), hyphen or en dash.
_LUMINAIRE = re.compile(r"^\s*((?:L\d+(?:\.\d+)?)|SNC)\s*[-\u2013]\s*lumin", re.I)


@dataclass(frozen=True)
class Link:
    key: str
    rule: str  # e.g. "board", "luminaire:L4.1"


def board_name(designation: str) -> str | None:
    """A board written as a name ("Q.E.G.", "Q.UPS 10kVA"), not a sentence ("Quadro elétrico…")."""
    name = re.sub(r"\s*\(.*?\)\s*$", "", designation).strip()
    upper = re.sub(r"kva\b", "KVA", name, flags=re.I)
    ok = _BOARD.match(name) and upper == upper.upper() and len(name) <= 30
    return name if ok else None


def _board(designation: str, folded: str) -> Link | None:
    return Link("ele.quadros", "board") if board_name(designation) else None


def _portinhola(designation: str, folded: str) -> Link | None:
    return Link("eq.portinhola", "portinhola") if "portinhola" in folded else None


def _ev_charger(designation: str, folded: str) -> Link | None:
    return Link("sys.ve", "ev_charger") if re.search(r"\bcarregador", folded) else None


def _pv_module(designation: str, folded: str) -> Link | None:
    return Link("sys.fv", "pv_module") if re.search(r"modulos? fotovolt", folded) else None


def _luminaire(designation: str, folded: str) -> Link | None:
    match = _LUMINAIRE.match(designation)
    return Link("eq.luminarias", f"luminaire:{match.group(1).upper()}") if match else None


RULES: tuple[Callable[[str, str], Link | None], ...] = (
    _luminaire,
    _board,
    _portinhola,
    _ev_charger,
    _pv_module,
)


def link_for(designation: str | None) -> Link | None:
    """The first rule that recognizes the article, or None."""
    if not designation:
        return None
    folded = fold(designation)
    for rule in RULES:
        found = rule(designation, folded)
        if found:
            return found
    return None
