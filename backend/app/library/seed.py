"""Proposed blocks and the archive from the reference projects (make seed-library, Phase 3).

Needs the source documents stored first (app.library.sources.seed_sources). Idempotent: proposed
blocks are rewritten from the documents; a block a curator approved or rejected is left as it
is. Every block the agent writes is "proposed".
"""

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import ficha_eletrotecnica
from app.ingest.detect import detect
from app.knowledge.sources import unique_files
from app.library.classify import ArchiveText, ProjectDoc, ProposedBlock, classify
from app.library.docx_blocks import split
from app.library.facts import Fact, cover_facts, ficha_facts, signature_facts
from app.library.rules import parse
from app.library.skeleton import SKELETON_ONLY, rule_for
from app.library.sources import reference_documents
from app.models import ArchiveChunk, ArchiveDoc, SourceDocument, SourceSection, TemplateBlock


def ficha_values(fixtures: Path, code: str) -> dict[str, Any]:
    """Values read from the ficha eletrotécnica of a reference project (in memory)."""
    for path in unique_files(fixtures / code):
        data = path.read_bytes()
        if detect(path.name, data).kind == "ficha_eletrotecnica":
            return {c.key: c.value for c in ficha_eletrotecnica.read(data).values}
    return {}


def project_docs(db: Session, fixtures: Path, code: str) -> dict[str, ProjectDoc]:
    """doc_type -> the split document of a project, its facts and its stored section ids."""
    values = ficha_values(fixtures, code)
    docs: dict[str, ProjectDoc] = {}
    for doc_type, _, data in reference_documents(fixtures, code):
        parts = split(data)
        facts: list[Fact] = ficha_facts(values)
        for section in parts.sections:
            if section.kind == "cover":
                facts += cover_facts(section.text.splitlines())
            elif section.kind == "signature":
                facts += signature_facts(section.text.splitlines())
        stored = db.scalars(
            select(SourceDocument).where(SourceDocument.sha256 == parts.sha256)
        ).first()
        ids = {s.order: str(s.id) for s in stored.sections} if stored else {}
        docs[doc_type] = ProjectDoc(code, parts, facts, ids)
    return docs


def with_skeleton(blocks: list[ProposedBlock], doc_type: str) -> list[ProposedBlock]:
    """Add the blocks of SPEC 8.3 no reference document has, empty, after their neighbour."""
    out = list(blocks)
    for item in SKELETON_ONLY:
        prefix = f"ele.{doc_type.lower()}."
        if not item.key.startswith(prefix) or any(b.key == item.key for b in out):
            continue
        at = next((i + 1 for i, b in enumerate(out) if b.key == item.after), len(out))
        out.insert(at, ProposedBlock(
            key=item.key, doc_type=doc_type, kind="block", level=item.level, title=item.title,
            order=0, mode="adaptive", entries=[], projects=[], source_refs=[], rels={},
            notes=["Esqueleto 8.3: nenhum projeto de referência tem este bloco; falta o texto."],
        ))  # fmt: skip
    for n, b in enumerate(out, start=1):
        b.order = n
    return out


def _write_evidence(db: Session, docs: list[ProjectDoc]) -> None:
    """What the curator sees of each source section (placeholders, personal data masked)."""
    for doc in docs:
        for order, units in doc.evidence.items():
            section_id = doc.section_ids.get(order)
            section = db.get(SourceSection, uuid.UUID(section_id)) if section_id else None
            if section is not None:
                section.units = units


def _write_blocks(db: Session, blocks: list[ProposedBlock]) -> int:
    existing = {
        (b.doc_type, b.key): b
        for b in db.scalars(select(TemplateBlock).where(TemplateBlock.version == 1))
    }
    written = 0
    for proposed in blocks:
        row = existing.pop((proposed.doc_type, proposed.key), None)
        if row is not None and row.status != "proposed":
            continue  # the curator decided: the agent does not touch it
        if row is None:
            row = TemplateBlock(key=proposed.key, doc_type=proposed.doc_type, version=1)
            db.add(row)
        row.kind, row.level, row.title = proposed.kind, proposed.level, proposed.title[:200]
        row.order, row.mode = proposed.order, proposed.mode
        row.body_template = [e.as_json() for e in proposed.entries]
        row.locked_ooxml = proposed.locked_ooxml
        row.ooxml_rels = proposed.rels
        row.required_keys = proposed.required_keys
        row.projects = proposed.projects
        row.source_refs = proposed.source_refs
        row.notes = proposed.notes
        row.activation_rule = rule_for(proposed.key)
        row.activation_ast = parse(row.activation_rule)
        row.archive_refs = (
            [f"arc:{p}:{proposed.key}" for p in proposed.projects]
            if any(e.mode == "adaptive" for e in proposed.entries)
            else []
        )
        written += 1
    for (doc_type, _), row in existing.items():
        if row.status == "proposed" and doc_type in {b.doc_type for b in blocks}:
            db.delete(row)  # no longer in the reference documents
    return written


def _write_archive(
    db: Session, texts: list[ArchiveText], sources: dict[tuple[str, str], str]
) -> int:
    for doc_type in {t.doc_type for t in texts}:
        for old in db.scalars(select(ArchiveDoc).where(ArchiveDoc.doc_type == doc_type)):
            db.delete(old)
    db.flush()
    docs: dict[tuple[str, str], ArchiveDoc] = {}
    for t in texts:
        doc = docs.get((t.project, t.doc_type))
        if doc is None:
            doc = ArchiveDoc(project_code=t.project, doc_type=t.doc_type,
                             source_document_id=sources[(t.project, t.doc_type)])  # fmt: skip
            db.add(doc)
            docs[(t.project, t.doc_type)] = doc
        doc.chunks.append(ArchiveChunk(block_key=t.block_key, order=t.order, text=t.text,
                                       source_section_id=t.section_id))  # fmt: skip
    return len(texts)


def seed_blocks(
    db: Session, fixtures: Path, codes: tuple[str, ...], doc_types: tuple[str, ...] = ("MDJ",)
) -> dict[str, int]:
    per_project = {c: project_docs(db, fixtures, c) for c in codes if (fixtures / c).is_dir()}
    sources = {(d.project_code, d.doc_type): str(d.id) for d in db.scalars(select(SourceDocument))}
    blocks = chunks = 0
    for doc_type in doc_types:
        docs = [p[doc_type] for p in per_project.values() if doc_type in p]
        proposed, archive = classify(doc_type, docs)
        proposed = with_skeleton(proposed, doc_type)
        _write_evidence(db, docs)
        blocks += _write_blocks(db, proposed)
        chunks += _write_archive(db, [a for a in archive if (a.project, doc_type) in sources],
                                 sources)  # fmt: skip
    db.flush()
    return {"blocks": blocks, "archive_chunks": chunks}
