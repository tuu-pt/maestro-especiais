"""Assemble the MDJ or the CTE of a project from the block library (SPEC 8.3, Phase 4).

Only from a confirmed revision of the ficha-base. For each block of the document type (in the
order of the library): the activation rule is evaluated on that revision; fixed paragraphs are
kept as the block's OOXML (locked); parametric ones get their placeholders resolved, with one
ValueRef per value; adaptive ones wait for the drafting step (Phase 4, LLM). A missing value
leaves the section "todo" with "falta dado"; a block the rule does not activate is kept, inactive,
with the reason. Sections built on a block not yet approved say so (block_status).
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.values import Resolved, ValueSource, label
from app.library.preview import revision_context
from app.library.rules import evaluate, explain, parse
from app.models import (
    Document,
    FichaRevision,
    Project,
    Section,
    SectionVersion,
    SourceDocument,
    TemplateBlock,
    ValueRef,
)

PLACEHOLDER = re.compile(r"\{\{v:([a-z0-9_.]+)\}\}")
MASK = "•••"
EMPTY_BLOCK = "Sem texto: nenhum projeto de referência tem este bloco (esqueleto 8.3)."
TEMPLATE_PROJECT = "R1"  # the package the draft .docx is built on [A CONFIRMAR: TUU template]


class AssemblyError(ValueError):
    """The document cannot be assembled (said to people as it is)."""


@dataclass
class Built:
    content: dict[str, Any]
    refs: list[ValueRef] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    pending: bool = False  # adaptive paragraphs still to write


def confirmed_revision(db: Session, project_id: uuid.UUID) -> FichaRevision | None:
    return db.scalars(
        select(FichaRevision)
        .where(FichaRevision.project_id == project_id, FichaRevision.status == "confirmed")
        .order_by(FichaRevision.confirmed_at.desc())
        .limit(1)
    ).first()


def value_mark(r: Resolved, anchor: str) -> dict[str, Any]:
    return {"type": "value", "attrs": {"key": r.key, "anchor": anchor, "label": label(r.key),
                                        "personal": r.personal, "missing": r.missing}}  # fmt: skip


def shown(r: Resolved) -> str:
    if r.missing:
        return f"[falta: {label(r.key)}]"
    if r.key == "doc.data":
        return "[data: pelo técnico]"
    if r.personal:
        return MASK
    return r.text or ""


def inline(text: str, values: ValueSource, entry: int, built: Built) -> list[dict[str, Any]]:
    """TipTap text nodes of one line, values as marked text (personal ones masked)."""
    nodes: list[dict[str, Any]] = []
    last = 0
    for m in PLACEHOLDER.finditer(text):
        if m.start() > last:
            nodes.append({"type": "text", "text": text[last : m.start()]})
        r = values.resolve(m.group(1))
        anchor = f"e{entry}-v{len(built.refs)}"
        built.refs.append(ValueRef(
            anchor=anchor, key=r.key, ficha_value_id=r.ficha_value_id, circuit_id=r.circuit_id,
            bom_item_id=r.bom_item_id, field=r.field, personal=r.personal,
            rendered_text=None if (r.personal or r.missing) else r.text,
        ))  # fmt: skip
        if r.missing and r.key not in built.missing:
            built.missing.append(r.key)
        nodes.append({"type": "text", "text": shown(r), "marks": [value_mark(r, anchor)]})
        last = m.end()
    if last < len(text):
        nodes.append({"type": "text", "text": text[last:]})
    return nodes


def build_content(block: TemplateBlock, values: ValueSource) -> Built:
    """The first version of a section: TipTap JSON from the block's paragraphs."""
    built = Built({"type": "doc", "content": []})
    nodes: list[dict[str, Any]] = built.content["content"]
    for i, e in enumerate(block.body_template):
        text = e.get("text") or ""
        if e["mode"] == "adaptive":
            built.pending = True
            nodes.append({"type": "pending", "attrs": {"entry": i, "note": e.get("note")}})
        elif e["mode"] == "fixed" or (e.get("ooxml") or "").startswith("<w:tbl"):
            lines = [inline(line, values, i, built) for line in text.split("\n")] if text else []
            attrs = {"entry": i, "parametric": e["mode"] != "fixed"}
            paragraphs = [{"type": "paragraph", "content": ln} for ln in lines]
            nodes.append({"type": "locked", "attrs": attrs, "content": paragraphs})
        else:
            for line in text.split("\n"):
                nodes.append({"type": "paragraph", "attrs": {"entry": i},
                              "content": inline(line, values, i, built)})  # fmt: skip
    return built


def template_for(db: Session, doc_type: str) -> SourceDocument | None:
    docs = db.scalars(select(SourceDocument).where(SourceDocument.doc_type == doc_type)).all()
    return next((d for d in docs if d.project_code == TEMPLATE_PROJECT), docs[0] if docs else None)


def assemble(
    db: Session, project: Project, doc_type: str, user_id: str | None,
    profile: dict[str, str] | None = None,
) -> Document:  # fmt: skip
    revision = confirmed_revision(db, project.id)
    if revision is None:
        raise AssemblyError("A ficha-base ainda não foi confirmada: não é possível montar peças.")
    blocks = db.scalars(
        select(TemplateBlock)
        .where(TemplateBlock.doc_type == doc_type, TemplateBlock.version == 1,
               TemplateBlock.status != "rejected")
        .order_by(TemplateBlock.order)
    ).all()  # fmt: skip
    if not blocks:
        raise AssemblyError(f"A biblioteca ainda não tem blocos do {doc_type} (make seed-library).")
    ctx, _ = revision_context(db, revision.id)
    values = ValueSource.load(db, revision, profile)
    template = template_for(db, doc_type)
    document = Document(
        project_id=project.id, type=doc_type, ficha_revision_id=revision.id,
        template_id=template.id if template else None, responsible_user_id=user_id,
    )  # fmt: skip
    for n, block in enumerate(blocks, start=1):
        tree = block.activation_ast or parse(block.activation_rule or "true")
        active = evaluate(tree, ctx)
        built = build_content(block, values)
        if not active:
            status, note = "todo", None
        elif not block.body_template:
            status, note = "todo", EMPTY_BLOCK
        elif built.missing:
            status = "todo"
            note = "Falta dado: " + ", ".join(label(k) for k in built.missing) + "."
        elif built.pending:
            status, note = "todo", "Por gerar: texto adaptativo."
        else:
            status, note = "generated", None
        slots = [{**s, "phase": 7, "equipment": None} for s in block.equipment_slots]
        document.sections.append(Section(
            block_id=block.id, block_key=block.key, block_version=block.version,
            block_status=block.status, order=n, title=block.title[:200], level=block.level,
            kind=block.kind, mode=block.mode, active=active,
            active_reason=None if active else explain(tree, ctx), status=status,
            status_note=note, missing_keys=built.missing, locked=block.mode == "fixed",
            equipment_slots=slots,
            versions=[SectionVersion(number=1, content=built.content, author_type="system",
                                     status="current", value_refs=built.refs)],
        ))  # fmt: skip
    db.add(document)
    db.flush()
    return document


def export_readiness(document: Document) -> list[dict[str, Any]]:
    """What stops the official export (Phase 6): an empty list means ready."""
    problems = []
    for s in document.sections:
        if not s.active:
            continue
        if s.block_status != "approved":
            problems.append({"section": s.order, "title": s.title, "reason": "bloco não aprovado"})
        if s.status != "reviewed":
            reason = s.status_note or "secção por rever"
            problems.append({"section": s.order, "title": s.title, "reason": reason})
    return problems
