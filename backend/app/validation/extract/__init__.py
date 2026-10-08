"""Collect the pieces of a project and read them (Phase 5, SPEC 8.1 step 5).

Each piece has a content hash: a revalidation reads again only the pieces whose content changed
(PieceFacts caches what was read). Reading is deterministic and never uses the LLM: what cannot
be read reliably becomes a fact marked "não comparável", with the reason.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, FichaRevision, PieceFacts, Project
from app.storage import ObjectStore
from app.validation.pieces import Piece, PieceData

# Bump when an extractor changes: every cached reading is then read again.
EXTRACTOR_VERSION = 2  # 2: luminaire types


@dataclass
class Sources:
    """What the extractors may need besides the piece itself."""

    db: Session
    store: ObjectStore | None
    revision: FichaRevision
    profile: dict[str, str]  # the technician's profile (tec.*), backend only


Extractor = Callable[[Sources, Piece], PieceData]
EXTRACTORS: dict[str, Extractor] = {}  # by Piece.origin, or "<origin>:<kind>"


def extractor(name: str) -> Callable[[Extractor], Extractor]:
    def decorator(fn: Extractor) -> Extractor:
        EXTRACTORS[name] = fn
        return fn

    return decorator


def digest(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def document_hash(document: Document) -> str:
    sections = []
    for s in document.sections:
        version = next((v for v in s.versions if v.number == s.current_version), None)
        sections.append([str(s.id), s.active, s.current_version,
                         version.content if version else None])  # fmt: skip
    return digest(EXTRACTOR_VERSION, str(document.ficha_revision_id), sections)


def collect(db: Session, project: Project, revision: FichaRevision) -> list[Piece]:
    """Every piece of the project the validation compares, assembled or not."""
    from app.validation.extract import documents, files  # registers the extractors

    pieces = [documents.piece(db, d) for d in db.scalars(
        select(Document).where(Document.project_id == project.id).order_by(Document.created_at)
    )]  # fmt: skip
    pieces += files.pieces(db, project, revision)
    return [p for p in pieces if p is not None]


def read(sources: Sources, project: Project, piece: Piece) -> tuple[PieceData, bool]:
    """What the piece says, from the cache when its content did not change. (data, re-read)"""
    db = sources.db
    cached = db.scalar(select(PieceFacts).where(
        PieceFacts.project_id == project.id, PieceFacts.piece_ref == piece.ref))  # fmt: skip
    if cached is not None and cached.content_hash == piece.content_hash:
        return PieceData.from_json(cached.data), False
    fn = EXTRACTORS.get(f"{piece.origin}:{piece.kind}") or EXTRACTORS[piece.origin]
    data = fn(sources, piece)
    if cached is None:
        cached = PieceFacts(project_id=project.id, piece_ref=piece.ref)
        db.add(cached)
    cached.content_hash = piece.content_hash
    cached.extractor_version = EXTRACTOR_VERSION
    cached.data = data.as_json()
    return data, True
