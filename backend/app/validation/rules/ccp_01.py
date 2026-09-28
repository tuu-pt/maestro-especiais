"""CCP-01 (SPEC 9): a brand or model without "ou equivalente" in public procurement (C5).

Only when the project is public procurement (Project.public_procurement). A paragraph of the
CTE or the MDJ that names a brand, a model, a series or a product reference and does not say
"ou equivalente" (or "equivalente", "similar") is flagged.
"""

import re

from app.ingest.detect import fold
from app.validation.compare import excerpt, paragraph_location
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, Finding, Rule

_NAMES = re.compile(r"\b(?:da marca|marca|modelo|serie|ref\.?|referencia)\b")
_EQUIVALENT = re.compile(r"\b(?:ou\s+)?(?:equivalente|similar|equiparad[oa])\b")


def check(ctx: Context) -> list[Finding]:
    if not ctx.project.public_procurement:
        return []
    out = []
    for p in ctx.paragraphs("CTE", "MDJ"):
        folded = fold(p.text)
        m = _NAMES.search(folded)
        if p.section_kind != "block" or m is None or _EQUIVALENT.search(folded):
            continue
        piece = ctx.pieces[p.piece]
        out.append(RULE.finding(
            f"{piece.name} · {p.section_title}: marca ou modelo sem «ou equivalente» "
            "(contratação pública).",
            key=f"{p.piece}|{p.section_key}|{p.index}",
            location=paragraph_location(ctx, p),
            evidence={"excerpt": excerpt(ctx, p.text, m.start(), m.end(), around=90)},
            suggested_fix="Acrescentar «ou equivalente» ou descrever só os requisitos mínimos.",
            actions=[OPEN_EDITOR],
        ))  # fmt: skip
    return out


RULE = Rule("CCP-01", "procurement", "warning", "Marca sem «ou equivalente»", check)
