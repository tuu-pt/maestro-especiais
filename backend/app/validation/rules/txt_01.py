"""TXT-01 (SPEC 9): line breaks in the middle of a sentence, repeated list items, duplicated
product references (information; C5, C13, C14).

- A paragraph that ends without punctuation followed, in the same section, by one that starts
  in lower case: a sentence broken by a line break (C13).
- The same item twice in a section, or two items of the list of legislation and standards that
  begin with the same three words (C14: two entries about Portuguese standards) [A CONFIRMAR].
- The same product reference twice in a paragraph ("Ref. 45070 S ou Ref. 45071 S, ou 45070 S").
"""

import re
from collections import Counter, defaultdict
from itertools import pairwise

from app.ingest.detect import fold
from app.validation.compare import excerpt, paragraph_location
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, Finding, Rule
from app.validation.pieces import Paragraph

LISTS = ("legislacao", "normas")
_REF = re.compile(r"\b(?:ref\.?\s*(?:ª|a)?\s*)?(\d{4,6}\s?[A-Z]{1,2})\b")
_ENDS = re.compile(r"[.:;!?)\]»\"”…]$")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


def _finding(ctx: Context, p: Paragraph, kind: str, message: str, n: int = 0,
             excerpt_text: str | None = None) -> Finding:  # fmt: skip
    piece = ctx.pieces[p.piece]
    return RULE.finding(
        f"{piece.name} · {p.section_title}: {message}",
        key=f"{kind}|{p.piece}|{p.section_key}|{p.index}|{n}",
        location=paragraph_location(ctx, p),
        evidence={"kind": kind, "excerpt": excerpt_text or excerpt(ctx, p.text, around=80)},
        actions=[OPEN_EDITOR],
    )


def check(ctx: Context) -> list[Finding]:
    out = []
    by_section: dict[tuple[str, str], list[Paragraph]] = defaultdict(list)
    for p in ctx.paragraphs("MDJ", "CTE"):
        if p.section_kind == "block":
            by_section[(p.piece, p.section_key)].append(p)
    for (_, key), paragraphs in by_section.items():
        for a, b in pairwise(paragraphs):
            first, second = a.text.strip(), b.text.strip()
            if (len(first) > 30 and first[-1].isalpha() and not _ENDS.search(first)
                    and second[:1].islower() and " | " not in first + second):  # fmt: skip
                joined = ctx.mask(f"…{first[-60:]} ⏎ {second[:60]}…")
                out.append(_finding(ctx, a, "break", "quebra de linha a meio de frase.",
                                    excerpt_text=joined))  # fmt: skip
        seen: dict[str, Paragraph] = {}
        openings: dict[tuple[str, ...], Paragraph] = {}
        for p in paragraphs:
            words = _words(p.text)
            if len(words) < 3:
                continue
            text = " ".join(words)
            if len(text) > 15 and text in seen:
                out.append(_finding(ctx, p, "repeated", "item repetido na mesma secção."))
            seen.setdefault(text, p)
            if any(s in key for s in LISTS):
                opening = tuple(words[:3])
                if opening in openings and openings[opening].text != p.text:
                    start = " ".join(p.text.split()[:3])
                    message = f"dois itens quase iguais na lista (começam por «{start}»)."
                    out.append(_finding(ctx, p, "near", message))
                openings.setdefault(opening, p)
    for p in ctx.paragraphs("MDJ", "CTE"):
        refs = Counter(" ".join(m.group(1).split()) for m in _REF.finditer(p.text))
        for n, (ref, times) in enumerate(sorted(refs.items())):
            if times > 1:
                out.append(_finding(ctx, p, "reference", f"referência de produto «{ref}» "
                                    f"repetida {times} vezes.", n))  # fmt: skip
    return out


RULE = Rule("TXT-01", "quality", "info", "Qualidade do texto", check)
