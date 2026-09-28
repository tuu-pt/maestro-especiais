"""Drafting of the adaptive paragraphs of a section with the LLM (SPEC 8.4, Phase 4).

The request carries the approved or proposed texts of the block in the archive (placeholders
already in, personal data masked), the keys of the ficha-base with their labels, and a few
non-personal values only as context, with the instruction to write every value as a
placeholder. The answer is validated (Pydantic) and post-processed:
- REF-01: a source outside the given set is removed;
- NUM-01: a digit outside a placeholder and outside the whitelist is flagged;
- a placeholder with no confirmed value is "falta dado";
- missing_data and assumptions go to the technician.
The result is always a new SectionVersion "proposed": nothing replaces the current text until a
person accepts it.
"""

import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assembly.assemble import Built, inline
from app.assembly.values import ValueSource
from app.ingest.keys import KEYS
from app.llm import prompts
from app.llm.client import LlmClient
from app.llm.numbers import stray_numbers
from app.llm.provider import Message
from app.models import (
    ArchiveChunk,
    ArchiveDoc,
    Citation,
    Document,
    FichaRevision,
    Project,
    Section,
    SectionVersion,
    TemplateBlock,
)
from app.profiles import revision_profile

PLACEHOLDER = re.compile(r"\{\{v:([a-z0-9_.]+)\}\}")
KEY = re.compile(r"[a-z]+\.[a-z0-9_.]+")
NUM_01 = "Número fora de marcador: confirmar ou trocar por um valor da ficha."
CONTEXT_PREFIXES = ("ele.", "sys.")  # never id.*: identification is only written by placeholder


class DraftParagraph(BaseModel):
    id: str = Field(max_length=20)
    text: str = Field(min_length=1, max_length=4000)
    sources: list[str] = Field(default_factory=list)


class DraftOutput(BaseModel):
    """The contract of SPEC 8.4."""

    block_key: str
    paragraphs: list[DraftParagraph] = Field(min_length=1, max_length=40)
    missing_data: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class DraftRefused(ValueError):
    """The section cannot be drafted (said to people as it is)."""


def current(section: Section) -> SectionVersion:
    return next(v for v in section.versions if v.number == section.current_version)


def node_text(node: dict[str, Any]) -> str:
    """Text of a node with its values back as placeholders (what the LLM may see)."""
    out = []
    children = node.get("content") or []
    if node.get("type") == "locked":
        children = [c for p in children for c in p.get("content") or []]
    for child in children:
        mark = next((m for m in child.get("marks") or [] if m["type"] == "value"), None)
        out.append("{{v:" + mark["attrs"]["key"] + "}}" if mark else child.get("text", ""))
    return "".join(out)


def adaptive_entries(block: TemplateBlock) -> list[int]:
    return [i for i, e in enumerate(block.body_template) if e["mode"] == "adaptive"]


def _is_adaptive_node(node: dict[str, Any], entries: set[int]) -> bool:
    attrs = node.get("attrs") or {}
    return node.get("type") == "pending" or bool(attrs.get("generated")) or (
        node.get("type") == "paragraph" and attrs.get("entry") in entries
    )  # fmt: skip


def build_request(
    db: Session, section: Section, block: TemplateBlock, project: Project, values: ValueSource,
    request: str | None = None,
) -> tuple[dict[str, Any], set[str]]:  # fmt: skip
    chunks = db.scalars(
        select(ArchiveChunk).join(ArchiveDoc).where(ArchiveChunk.block_key == section.block_key)
        .order_by(ArchiveDoc.project_code)
    ).all()  # fmt: skip
    sources = [{"id": c.ref, "text": c.text} for c in chunks]
    version = current(section)
    entries = set(adaptive_entries(block))
    nodes = version.content.get("content") or []
    fixed = [t for n in nodes if not _is_adaptive_node(n, entries) and (t := node_text(n)).strip()]
    context = []
    for key, fv in sorted(values.values.items()):
        scalar = isinstance(fv.value, str | int | float) and not isinstance(fv.value, bool)
        if key.startswith(CONTEXT_PREFIXES) and not fv.personal_data and scalar and key in KEYS:
            context.append({"key": key, "value": fv.value})
    kind = {k: values.values[k].value for k in ("ele.descricao_imovel", "ele.classificacao",
                                                "ele.tipo_utilizacao", "ele.instalacao")
            if k in values.values}  # fmt: skip
    body: dict[str, Any] = {
        "block_key": block.key, "title": block.title,
        "project": {"tipo": kind, "fase": project.phase},
        "fixed_paragraphs": fixed, "sources": sources,
        "keys": values.available(), "context_values": context,
    }  # fmt: skip
    if request:
        body["request"] = request
        body["current_paragraphs"] = [
            node_text(n)
            for n in nodes
            if _is_adaptive_node(n, entries) and n["type"] == "paragraph"
        ]
    return body, {s["id"] for s in sources}


def postprocess(
    output: DraftOutput, allowed: set[str], values: ValueSource
) -> tuple[list[DraftParagraph], list[dict[str, Any]], list[str]]:
    issues: list[dict[str, Any]] = []
    paragraphs = []
    # a key the model says is missing but that has a value in the ficha-base is not missing
    missing = [m for m in dict.fromkeys(output.missing_data) if m and not (
        KEY.fullmatch(m) and not values.resolve(m).missing)]  # fmt: skip
    for p in output.paragraphs:
        kept = [s for s in p.sources if s in allowed]
        issues += [{"rule": "REF-01", "paragraph": p.id, "source": s,
                    "message": "Fonte fora do conjunto fornecido: removida."}
                   for s in p.sources if s not in allowed]  # fmt: skip
        issues += [{"rule": "NUM-01", "paragraph": p.id, "snippet": snippet,
                    "message": NUM_01}
                   for snippet in stray_numbers(p.text)]  # fmt: skip
        for key in PLACEHOLDER.findall(p.text):
            if values.resolve(key).missing and key not in missing:
                missing.append(key)
        paragraphs.append(DraftParagraph(id=p.id, text=p.text, sources=kept))
    return paragraphs, issues, missing


def propose(
    db: Session, section: Section, block: TemplateBlock, values: ValueSource,
    paragraphs: list[DraftParagraph], *, request: str | None, llm_call_id: uuid.UUID | None,
    missing: list[str], assumptions: list[str], issues: list[dict[str, Any]],
) -> SectionVersion:  # fmt: skip
    entries = adaptive_entries(block)
    first = entries[0] if entries else 0
    built = Built({"type": "doc", "content": []})
    generated: list[dict[str, Any]] = []
    citations: list[Citation] = []
    for n, p in enumerate(paragraphs):
        content = inline(p.text, values, first, built)
        for node in content:
            node.setdefault("marks", []).append({"type": "generated"})
        anchor = f"g{n}"
        generated.append({"type": "paragraph", "attrs": {"entry": first, "generated": True,
                          "anchor": anchor, "sources": p.sources}, "content": content})  # fmt: skip
        citations += [Citation(anchor=anchor, kind="archive", target_id=s) for s in p.sources]
    nodes: list[dict[str, Any]] = []
    placed = False
    for node in current(section).content.get("content") or []:
        if _is_adaptive_node(node, set(entries)):
            if not placed:
                nodes += generated
                placed = True
            continue
        nodes.append(node)
    if not placed:
        nodes += generated
    number = (db.scalar(select(func.max(SectionVersion.number)).where(
        SectionVersion.section_id == section.id)) or 0) + 1  # fmt: skip
    version = SectionVersion(
        section_id=section.id, number=number, content={"type": "doc", "content": nodes},
        author_type="agent", status="proposed", llm_call_id=llm_call_id, request=request,
        missing_data=missing, assumptions=assumptions, issues=issues, value_refs=built.refs,
        citations=citations,
    )  # fmt: skip
    db.add(version)
    section.status_note = "Proposta do agente por aceitar."
    db.flush()
    return version


def draft_section(
    db: Session, client: LlmClient, section: Section, request: str | None = None
) -> SectionVersion:
    """One request to the LLM for the adaptive paragraphs of a section: a proposed version."""
    document = db.get(Document, section.document_id)
    block = db.get(TemplateBlock, section.block_id) if section.block_id else None
    if document is None or block is None:
        raise DraftRefused("Secção sem bloco da biblioteca.")
    if not adaptive_entries(block):
        raise DraftRefused("Os blocos fixos e paramétricos não passam pelo LLM.")
    if not section.active:
        raise DraftRefused("A secção não está ativa: ative-a com justificação antes de a redigir.")
    project = db.get(Project, document.project_id)
    revision = db.get(FichaRevision, document.ficha_revision_id)
    assert project is not None and revision is not None
    profile = revision_profile(db, client.settings, revision)
    values = ValueSource.load(db, revision, profile)
    body, allowed = build_request(db, section, block, project, values, request)
    prompt = prompts.REWRITE if request else prompts.ADAPTIVE
    output, call = client.generate(
        db, project=project, purpose="drafting", prompt_version=prompt,
        system=prompts.load(prompt), schema=DraftOutput, section_id=section.id, profile=profile,
        messages=[Message("user", json.dumps(body, ensure_ascii=False, default=str))],
    )  # fmt: skip
    paragraphs, issues, missing = postprocess(output, allowed, values)
    return propose(db, section, block, values, paragraphs, request=request, llm_call_id=call.id,
                   missing=missing, assumptions=output.assumptions, issues=issues)  # fmt: skip


def accept(db: Session, version: SectionVersion, user_id: str) -> Section:
    section = version.section
    for v in section.versions:
        if v.status == "current":
            v.status = "superseded"
    version.status = "current"
    section.current_version = version.number
    section.reviewed_by = section.reviewed_at = None
    if version.missing_data or any(r.rendered_text is None and not r.personal
                                   for r in version.value_refs):  # fmt: skip
        section.status = "todo"
        section.status_note = "Falta dado: " + ", ".join(version.missing_data) + "."
    else:
        section.status, section.status_note = "generated", None
    db.flush()
    return section


def reject(db: Session, version: SectionVersion) -> Section:
    version.status = "rejected"
    section = version.section
    if not any(v.status == "proposed" for v in section.versions):
        section.status_note = None if section.status == "generated" else section.status_note
    db.flush()
    return section
