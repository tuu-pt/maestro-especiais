"""Accent- and case-insensitive text folding that keeps a map back to the original."""

import unicodedata

# Underscores count as spaces so that file names like "Termo_Joao_Silva" still match.
_SPACE_LIKE = frozenset(" \t\r\n\u00a0\u2007\u202f_")


def fold(text: str) -> tuple[str, list[int]]:
    """Return (folded, index) where index[i] is the original position of folded[i].

    Folding strips accents, casefolds and collapses runs of whitespace into one space.
    index has one extra trailing entry equal to len(text).
    """
    out: list[str] = []
    index: list[int] = []
    previous_space = False
    for i, ch in enumerate(text):
        if ch in _SPACE_LIKE or ch.isspace():
            if not previous_space:
                out.append(" ")
                index.append(i)
            previous_space = True
            continue
        previous_space = False
        decomposed = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
        for c in base or ch:
            out.append(c)
            index.append(i)
    index.append(len(text))
    return "".join(out), index


def fold_simple(text: str) -> str:
    return fold(text)[0].strip()


def original_span(index: list[int], start: int, end: int) -> tuple[int, int]:
    """Map a [start, end) span of the folded text back to the original text."""
    return index[start], index[end - 1] + 1


def digits_only(text: str) -> str:
    return "".join(c for c in text if c in "0123456789")
