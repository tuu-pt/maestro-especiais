"""The MDJ and the CTE assembled by the tool: paragraphs, sections and their values (Phase 5).

Values come from the value marks (ValueRef): a value edited by hand is a fact of its own, marked
for the COE-01; the others are the ficha-base values by construction. Personal values are
resolved here, in the backend, and are masked in every evidence.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.assembly.values import ValueSource
from app.drafting.draft import node_text
from app.ingest.written import section_lines
from app.library import docx_blocks
from app.models import Document, ProjectFile, Section, SectionVersion
from app.validation.extract import (
    EXTRACTOR_VERSION,
    Sources,
    digest,
    document_hash,
    extractor,
)
from app.validation.extract import text as text_facts
from app.validation.pieces import Fact, Paragraph, Piece, PieceData, SectionInfo

PREFIX = {"MDJ": "ele.mdj.", "CTE": "ele.cte."}


def piece(db: Session, document: Document) -> Piece | None:
    if document.type not in PREFIX:
        return None  # the forms are read from their files
    if document.origin == "existing":
        file = db.get(ProjectFile, document.source_file_id) if document.source_file_id else None
        if file is None:
            return None
        return Piece(
            ref=f"doc:{document.id}", kind=document.type, origin="existing",
            content_hash=digest(EXTRACTOR_VERSION, file.checksum), date=file_date(file),
            document_id=str(document.id), file_id=str(file.id),
        )  # fmt: skip
    return Piece(
        ref=f"doc:{document.id}", kind=document.type, origin="assembled",
        content_hash=document_hash(document), document_id=str(document.id),
    )  # fmt: skip


def file_date(file: ProjectFile) -> str:
    """The date of the file if it says one, otherwise the day it was uploaded."""
    return (file.file_date or file.created_at.date()).isoformat()


def current(section: Section) -> SectionVersion | None:
    return next((v for v in section.versions if v.number == section.current_version), None)


def section_key(document_type: str, block_key: str) -> str:
    prefix = PREFIX.get(document_type, "")
    return block_key[len(prefix) :] if block_key.startswith(prefix) else block_key


def _plain(node: dict[str, Any]) -> str:
    if node.get("type") == "text":
        return str(node.get("text", ""))
    return "".join(_plain(c) for c in node.get("content") or [])


def _blocks(content: dict[str, Any]) -> list[dict[str, Any]]:
    """Top-level paragraphs, with the paragraphs of locked nodes one by one."""
    out = []
    for node in content.get("content") or []:
        if node.get("type") == "locked":
            out += [{**p, "attrs": {**(p.get("attrs") or {}), "locked": True}}
                    for p in node.get("content") or []]  # fmt: skip
        elif node.get("type") != "pending":
            out.append(node)
    return out


def _generated(node: dict[str, Any]) -> bool:
    if (node.get("attrs") or {}).get("generated"):
        return True
    return any(m.get("type") == "generated" for c in node.get("content") or []
               for m in c.get("marks") or [])  # fmt: skip


def _value_facts(node: dict[str, Any], piece_ref: str, where: dict[str, Any],
                 version: SectionVersion, values: ValueSource) -> list[Fact]:  # fmt: skip
    refs = {r.anchor: r for r in version.value_refs}
    facts = []
    for child in node.get("content") or []:
        mark = next((m for m in child.get("marks") or [] if m.get("type") == "value"), None)
        if mark is None:
            continue
        attrs = mark["attrs"]
        ref = refs.get(attrs.get("anchor"))
        key = attrs["key"]
        edited = bool(ref and ref.edited and ref.edited.get("coe_01"))
        if edited:
            value: Any = child.get("text", "")
        else:
            resolved = values.resolve(key)
            if resolved.missing:
                continue
            value = resolved.text
        personal = bool(attrs.get("personal"))
        facts.append(Fact(
            key=key, value=value, piece=piece_ref, personal=personal,
            locator={**where, "anchor": attrs.get("anchor")},
            note="valor editado à mão" if edited else "valor da ficha-base (marcador)",
            shown=None if personal else str(value),
        ))  # fmt: skip
    return facts


@extractor("assembled")
def read_assembled(sources: Sources, piece: Piece) -> PieceData:
    document = sources.db.get(Document, piece.document_id)
    data = PieceData()
    if document is None:
        return data
    values = ValueSource.load(sources.db, sources.revision, sources.profile)
    for s in document.sections:
        key = section_key(document.type, s.block_key)
        data.sections.append(SectionInfo(piece.ref, key, s.title, s.kind, s.level, s.active,
                                         str(s.id)))  # fmt: skip
        version = current(s)
        if not s.active or version is None:
            continue
        for i, node in enumerate(_blocks(version.content)):
            text = _plain(node)
            if not text.strip():
                continue
            where = {"section": key, "section_title": s.title, "paragraph": i,
                     "section_id": str(s.id)}  # fmt: skip
            data.paragraphs.append(Paragraph(
                piece=piece.ref, section_key=key, section_title=s.title, section_kind=s.kind,
                index=i, text=text, source_text=node_text(node), generated=_generated(node),
                anchor=(node.get("attrs") or {}).get("anchor"), section_id=str(s.id),
            ))  # fmt: skip
            data.facts += _value_facts(node, piece.ref, where, version, values)
    data.facts += text_facts.read(data.paragraphs, piece.ref, with_identification=False)
    return data


@extractor("existing")
def read_existing(sources: Sources, piece: Piece) -> PieceData:
    """A piece made by hand: the original file, split as in Phase 3 (values in the clear)."""
    data = PieceData()
    file = sources.db.get(ProjectFile, piece.file_id)
    if file is None or sources.store is None:
        data.warnings.append("Ficheiro original indisponível: a peça não foi lida.")
        return data
    try:
        parts = docx_blocks.split(sources.store.get(file.storage_key))
    except docx_blocks.DocxError:
        data.warnings.append("Documento Word ilegível: a peça não foi lida.")
        return data
    data.warnings += parts.warnings
    for s in parts.sections:
        data.sections.append(SectionInfo(piece.ref, s.key, s.title, s.kind, s.level))
        for i, line in enumerate(section_lines(s.elements)):
            data.paragraphs.append(Paragraph(
                piece=piece.ref, section_key=s.key, section_title=s.title, section_kind=s.kind,
                index=i, text=line, anchor=f"p{i}",
            ))  # fmt: skip
    data.facts = text_facts.read(data.paragraphs, piece.ref, with_identification=True)
    return data
