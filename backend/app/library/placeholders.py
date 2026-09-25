"""Replace the known values of a project by {{v:<key>}} inside the OOXML of a section.

A value split across runs is joined into the first run it touches (keeping that run's
formatting); only the text of the value moves, the rest of the runs stays as it was.
"""

import copy
from dataclasses import dataclass
from typing import Any

from lxml import etree

from app.library.docx_blocks import w
from app.library.facts import Fact

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


@dataclass
class Substituted:
    element: Any  # a copy of the original, with placeholders
    keys: list[str]  # in order of appearance
    text: str  # paragraph texts joined by "\n"

    @property
    def ooxml(self) -> str:
        return etree.tostring(self.element, encoding="unicode")


def _own_texts(p: Any) -> list[Any]:
    """w:t of this paragraph only (not of paragraphs nested in text boxes)."""
    return [t for t in p.iter(w("t")) if next(t.iterancestors(w("p")), None) is p]


def _spans(text: str, facts: list[Fact], scope: str) -> list[tuple[int, int, Fact]]:
    """Longest value first; for equal lengths, facts of this scope, then the given order."""
    chosen: list[tuple[int, int, Fact]] = []
    ranked = sorted(enumerate(facts), key=lambda x: (-len(x[1].value), x[1].scope != scope, x[0]))
    for _, fact in ranked:
        for m in fact.pattern.finditer(text):
            start, end = m.span(1) if m.groups() else m.span()
            if all(end <= s or start >= e for s, e, _ in chosen):
                chosen.append((start, end, fact))
    return sorted(chosen, key=lambda c: c[0])


def _replace(texts: list[Any], start: int, end: int, replacement: str) -> None:
    offset = 0
    placed = False
    for t in texts:
        value = t.text or ""
        a, b = offset, offset + len(value)
        offset = b
        if b <= start or a >= end:
            continue
        s, e = max(start, a) - a, min(end, b) - a
        if not placed:
            t.text = value[:s] + replacement + value[e:]
            placed = True
        else:
            t.text = value[:s] + value[e:]
        t.set(XML_SPACE, "preserve")


def substitute(element: Any, facts: list[Fact], scope: str = "document") -> Substituted:
    """A copy of element with every known value replaced (facts of other scopes are ignored)."""
    usable = [f for f in facts if f.scope == "document" or f.scope == scope]
    copied = copy.deepcopy(element)
    keys: list[str] = []
    lines: list[str] = []
    paragraphs = list(copied.iter(w("p")))  # itself, cells and text boxes
    for p in paragraphs:
        texts = _own_texts(p)
        text = "".join(t.text or "" for t in texts)
        spans = _spans(text, usable, scope)
        for start, end, fact in reversed(spans):
            _replace(texts, start, end, fact.placeholder)
        keys += [fact.key for _, _, fact in spans]
        line = "".join(t.text or "" for t in texts)
        if line.strip():
            lines.append(line)
    return Substituted(copied, keys, "\n".join(lines))
