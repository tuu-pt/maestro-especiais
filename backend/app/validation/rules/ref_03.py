"""REF-03 (SPEC 9): an incomplete reference, e.g. "secção das RTIEBT" without its number (C11)."""

from app.validation import citations
from app.validation.compare import excerpt, paragraph_location
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, Finding, Rule


def check(ctx: Context) -> list[Finding]:
    out = []
    for p in ctx.paragraphs("MDJ", "CTE"):
        for n, m in enumerate(citations.incomplete(p.text)):
            piece = ctx.pieces[p.piece]
            out.append(RULE.finding(
                f"{piece.name} · {p.section_title}: «{m.group(0)}» sem o número da secção.",
                key=f"{p.piece}|{p.section_key}|{p.index}|{n}",
                location=paragraph_location(ctx, p),
                evidence={"excerpt": excerpt(ctx, p.text, m.start(), m.end())},
                suggested_fix="Indicar a secção (ex.: secção 801.2.1.3.2.1 das RTIEBT) ou retirar.",
                actions=[OPEN_EDITOR],
            ))  # fmt: skip
    return out


RULE = Rule("REF-03", "references", "warning", "Referência incompleta", check)
