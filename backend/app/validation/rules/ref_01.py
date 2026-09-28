"""REF-01 (SPEC 9): a citation or source that is not in the corpus or was not provided.

The drafting removes a source outside the set it gave the agent (Phase 4, `outside`); the
validation checks every citation of the agent's text in the pieces against the archive and the
corpus (critical). A diploma or standard written in the text that is not in the corpus is a
warning, with a request to the curator (D-d, [A CONFIRMAR]): the corpus is still a list.
"""

from collections.abc import Iterable

from sqlalchemy import select

from app.models import ArchiveChunk, Citation, Section, SectionVersion
from app.validation import citations
from app.validation.compare import excerpt, paragraph_location
from app.validation.context import Context
from app.validation.core import ASK_CURATOR, OPEN_EDITOR, Finding, Rule

REMOVED = "Fonte fora do conjunto fornecido: removida."


def outside(sources: Iterable[str], allowed: set[str]) -> list[str]:
    """The sources the agent gave that were not among the ones it was given."""
    return [s for s in sources if s not in allowed]


def _known(ctx: Context, kind: str, target: str) -> bool:
    if kind == "archive":
        code_key = target.split(":", 2)
        if len(code_key) != 3:
            return False
        return any(c.ref == target for c in ctx.db.scalars(
            select(ArchiveChunk).where(ArchiveChunk.block_key == code_key[2])))  # fmt: skip
    if kind == "regulation":
        return any(r.code == target or str(r.id) == target for r in ctx.regulations)
    return True  # ficha, calc, block: resolved by the backend itself


def check(ctx: Context) -> list[Finding]:
    out = []
    for piece in ctx.of_kind("MDJ", "CTE"):
        if piece.origin != "assembled":
            continue
        rows = ctx.db.execute(
            select(Citation, Section)
            .join(SectionVersion, Citation.section_version_id == SectionVersion.id)
            .join(Section, SectionVersion.section_id == Section.id)
            .where(Section.document_id == piece.document_id,
                   SectionVersion.number == Section.current_version)
        ).all()  # fmt: skip
        for citation, section in rows:
            if _known(ctx, citation.kind, citation.target_id):
                continue
            out.append(RULE.finding(
                f"{piece.name} · {section.title}: cita uma fonte que não existe no corpus nem "
                "no arquivo.",
                key=f"{piece.ref}|{section.id}|{citation.anchor}|{citation.target_id}",
                location={"piece": piece.ref, "section_title": section.title,
                          "section_id": str(section.id), "anchor": citation.anchor},
                evidence={"source": citation.target_id, "kind": citation.kind},
                likely_reading="Fonte inventada ou removida do corpus.",
                suggested_fix="Retirar a citação ou citar um documento do corpus.",
                actions=[OPEN_EDITOR],
            ))  # fmt: skip
    return out + in_text(ctx)


def in_text(ctx: Context) -> list[Finding]:
    out = []
    for p in ctx.paragraphs("MDJ", "CTE"):
        for c in citations.find(p.text):
            if c.code is not None:
                continue
            piece = ctx.pieces[p.piece]
            out.append(RULE.finding(
                f"{piece.name} · {p.section_title}: «{c.text}» não está no corpus.",
                key=f"text|{p.piece}|{p.section_key}|{p.index}|{c.text.lower()}",
                severity="warning", location=paragraph_location(ctx, p),
                evidence={"citation": c.text,
                          "excerpt": excerpt(ctx, p.text, c.start, c.start + len(c.text))},
                likely_reading="Documento por acrescentar ao corpus: pedir ao curador.",
                actions=[ASK_CURATOR, OPEN_EDITOR],
            ))  # fmt: skip
    return out


RULE = Rule("REF-01", "references", "critical", "Citação sem fonte no corpus", check)
