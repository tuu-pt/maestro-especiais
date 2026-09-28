"""The likely reading of a divergence (SPEC 9), deterministic.

- Only one piece differs from the ficha-base: that piece is the suspect ("erro provável no CTE").
- The piece that differs is more recent than the ficha-base: the suspect is the ficha-base, and
  the proposal is to update the ficha, not the pieces (P5, COE-02).
- Several pieces differ: the reading says so and asks to confirm; it never decides by majority.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.validation.pieces import Fact, Piece

NEWER_THAN_FICHA = (
    "{name} é mais recente do que a ficha-base e diverge dela: a suspeita é a ficha-base "
    "(propor atualizar a ficha, não as peças)."
)


@dataclass
class Observation:
    piece: Piece
    fact: Fact


@dataclass
class Divergence:
    reference: Any  # the ficha-base value (None: the ficha-base has none)
    agreeing: list[Observation]
    divergent: list[Observation]

    @property
    def pieces(self) -> list[Piece]:
        return [o.piece for o in self.divergent]


def split(
    reference: Any,
    observations: Sequence[Observation],
    same: Callable[[Any, Any], bool] = lambda a, b: a == b,
) -> Divergence:
    agreeing = [o for o in observations if same(o.fact.value, reference)]
    divergent = [o for o in observations if not same(o.fact.value, reference)]
    return Divergence(reference, agreeing, divergent)


def newer(piece: Piece, ficha_date: str | None) -> bool:
    return bool(piece.date and ficha_date and piece.date > ficha_date)


def reading(d: Divergence, ficha_date: str | None) -> str | None:
    if not d.divergent:
        return None
    pieces = list(dict.fromkeys(o.piece.ref for o in d.divergent))
    if len(pieces) == 1:
        piece = d.divergent[0].piece
        if newer(piece, ficha_date):
            return NEWER_THAN_FICHA.format(name=_capital(piece.name))
        return f"Erro provável {piece.in_label}."
    names = ", ".join(dict.fromkeys(o.piece.name for o in d.divergent))
    if d.reference is None:
        return f"A ficha-base não tem este valor e as peças divergem entre si ({names}): confirmar."
    return f"Várias peças divergem da ficha-base ({names}): confirmar a ficha-base e cada peça."


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]
