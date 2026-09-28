"""Quantities written in the pieces, read without the LLM (Phase 5).

- Numbers in digits or in Portuguese words, up to the hundreds ("seis", "dezasseis",
  "vinte e dois").
- One multiplication, only in the fixed form "N <container> com (capacidade de|capacidade para)
  M <object> (individuais)? (em|por)? cada": "três pedestais com capacidade de dois carregadores
  individuais em cada" = 3 x 2 = 6 (C8). Nothing else is multiplied.
- A quantity that is a part of another ("dos quais 2 são de instalação obrigatória") is not the
  quantity of the whole: only the first "N <object>" of a sentence counts.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.ingest.detect import fold

TIMES = "\u00d7"  # the multiplication sign shown to people

UNITS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "catorze": 14, "quatorze": 14, "quinze": 15, "dezasseis": 16, "dezesseis": 16,
    "dezassete": 17, "dezessete": 17, "dezoito": 18, "dezanove": 19, "dezenove": 19,
}  # fmt: skip
TENS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
        "setenta": 70, "oitenta": 80, "noventa": 90}  # fmt: skip
HUNDREDS = {"cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200, "trezentos": 300,
            "trezentas": 300, "quatrocentos": 400, "quinhentos": 500}  # fmt: skip
_WORD = "|".join(sorted([*UNITS, *TENS, *HUNDREDS], key=len, reverse=True))
# a number: digits, or words joined by "e" ("vinte e dois", "cento e vinte")
NUMBER = rf"(?:\d+|(?:{_WORD})(?:\s+e\s+(?:{_WORD}))*)"


def to_int(text: str) -> int | None:
    """ "16" → 16; "dezasseis" → 16; "vinte e dois" → 22; anything else → None."""
    t = fold(text).strip()
    if t.isdigit():
        return int(t)
    total = 0
    for part in re.split(r"\s+e\s+", t):
        value = UNITS.get(part, TENS.get(part, HUNDREDS.get(part)))
        if value is None:
            return None
        total += value
    return total


def fold_in_place(text: str) -> str:
    """Lower case, no accents, same length (offsets stay valid in the original text)."""
    out = []
    for c in text:
        base = unicodedata.normalize("NFKD", c)[:1].lower()
        out.append(base if len(base) == 1 else c)
    return "".join(out)


@dataclass(frozen=True)
class Quantity:
    value: int
    text: str  # the words as they are in the piece
    how: str  # "lido", or "3 x 2 (multiplicação escrita na peça)" (TIMES)
    start: int


def count(text: str, noun: str, container: str | None = None) -> Quantity | None:
    """The quantity of <noun> in a sentence: the multiplication form first, then "N <noun>".

    noun and container are folded regular expressions (e.g. r"carregador(?:es)?").
    """
    folded = fold_in_place(text)
    if container:
        m = re.search(
            rf"\b({NUMBER})\s+{container}\s+(?:\w+\s+){{0,2}}com\s+(?:capacidade\s+(?:de|para)\s+)?"
            rf"({NUMBER})\s+{noun}(?:\s+\w+)?\s+(?:em\s+|por\s+)?cada\b",
            folded,
        )
        if m:
            a, b = to_int(m.group(1)), to_int(m.group(2))
            if a is not None and b is not None:
                how = f"{a} {TIMES} {b} (multiplicação escrita na peça)"
                return Quantity(a * b, text[m.start():m.end()], how, m.start())  # fmt: skip
    for m in re.finditer(rf"\b({NUMBER})\s+(?:novos?\s+|novas?\s+)?{noun}\b", folded):
        before = folded[max(0, m.start() - 12) : m.start()]
        if re.search(r"\b(?:dos|das)\s+quais\s*$", before):
            continue  # a part of the whole
        value = to_int(m.group(1))
        if value is not None:
            return Quantity(value, text[m.start() : m.end()], "lido", m.start())
    return None
