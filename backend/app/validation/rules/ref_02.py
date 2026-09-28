"""REF-02 (SPEC 9): a cited document that is revoked or not citable.

A document of the corpus the curator marked revoked is critical. One not yet confirmed by the
curator (everything, while D7 is pending) is information, once per piece with the list of
documents, so that it does not hide the rest (D-d, [A CONFIRMAR]).
"""

from collections import defaultdict

from app.validation import citations
from app.validation.compare import excerpt, paragraph_location
from app.validation.context import Context
from app.validation.core import ASK_CURATOR, OPEN_EDITOR, Finding, Rule


def check(ctx: Context) -> list[Finding]:
    corpus = {r.code: r for r in ctx.regulations}
    out = []
    pending: dict[str, set[str]] = defaultdict(set)
    for p in ctx.paragraphs("MDJ", "CTE"):
        for c in citations.find(p.text):
            doc = corpus.get(c.code) if c.code else None
            if doc is None:
                continue  # not in the corpus: REF-01
            if doc.status == "revoked":
                piece = ctx.pieces[p.piece]
                out.append(RULE.finding(
                    f"{piece.name} · {p.section_title}: cita «{doc.title}», que está revogado.",
                    key=f"revoked|{p.piece}|{p.section_key}|{p.index}|{doc.code}",
                    location=paragraph_location(ctx, p),
                    evidence={"citation": c.text, "document": doc.title,
                              "excerpt": excerpt(ctx, p.text, c.start, c.start + len(c.text))},
                    likely_reading="Referência desatualizada.",
                    suggested_fix="Citar o documento em vigor que o substitui.",
                    actions=[OPEN_EDITOR],
                ))  # fmt: skip
            elif not doc.citable:
                pending[p.piece].add(doc.title)
    for ref, titles in pending.items():
        piece = ctx.pieces[ref]
        out.append(RULE.finding(
            f"{piece.name}: cita {len(titles)} documento(s) do corpus ainda por confirmar pelo "
            "curador (D7).",
            key=f"pending|{ref}", severity="info",
            location={"piece": ref, "piece_name": piece.name, "document_id": piece.document_id},
            evidence={"documents": sorted(titles)},
            likely_reading="Aguarda curador: nenhum documento do corpus está marcado como citável.",
            actions=[ASK_CURATOR],
        ))  # fmt: skip
    return out


RULE = Rule("REF-02", "references", "critical", "Documento revogado ou não citável", check)
