"""Documents of a project (SPEC 7.3, screen D): assemble, read, draft .docx, export check."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.assembly.assemble import AssemblyError, assemble, confirmed_revision, export_readiness
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Document, FichaRevision, Project
from app.profiles import revision_profile
from app.review import revision_label
from app.storage import ObjectStore, get_store

router = APIRouter(tags=["documentos"])

DB = Annotated[Session, Depends(get_session)]
Store = Annotated[ObjectStore, Depends(get_store)]
Config = Annotated[Settings, Depends(get_settings)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class AssembleIn(BaseModel):
    type: Literal["MDJ", "CTE"]


class SectionOut(BaseModel):
    id: uuid.UUID
    order: int
    title: str
    level: int
    kind: str
    mode: str
    block_key: str
    block_status: str
    block_approved: bool
    active: bool
    active_reason: str | None
    status: str
    status_note: str | None
    missing_keys: list[str]
    locked: bool
    equipment_slots: list[dict[str, Any]]
    current_version: int
    content: dict[str, Any]
    has_adaptive: bool
    proposals: int
    unlocked: dict[str, Any] | None
    activation_override: dict[str, Any] | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    missing_data: list[Any]
    assumptions: list[Any]
    issues: list[Any]
    citations: list[dict[str, Any]]


class DocumentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    origin: str  # assembled | existing (read-only, Phase 5)
    source_file_id: uuid.UUID | None = None
    status: str  # draft | in_review | approved
    revision_label: str = "A"  # rev. A, B… (Phase 6)
    responsible_user_id: str | None = None
    ficha_revision: str
    created_at: datetime
    counts: dict[str, int]
    sections: list[SectionOut] | None = None


def _out(db: Session, d: Document, with_sections: bool = True) -> DocumentOut:
    revision = db.get(FichaRevision, d.ficha_revision_id)
    counts: dict[str, int] = {"sections": len(d.sections)}
    for s in d.sections:
        counts[s.status if s.active else "inactive"] = (
            counts.get(s.status if s.active else "inactive", 0) + 1
        )
        if s.block_status != "approved":
            counts["not_approved"] = counts.get("not_approved", 0) + 1
    sections = None
    if with_sections:
        sections = []
        for s in d.sections:
            version = next(v for v in s.versions if v.number == s.current_version)
            sections.append(SectionOut(
                id=s.id, order=s.order, title=s.title, level=s.level, kind=s.kind, mode=s.mode,
                block_key=s.block_key, block_status=s.block_status,
                block_approved=s.block_status == "approved", active=s.active,
                active_reason=s.active_reason, status=s.status, status_note=s.status_note,
                missing_keys=s.missing_keys, locked=s.locked, equipment_slots=s.equipment_slots,
                current_version=s.current_version, content=version.content,
                has_adaptive=s.mode == "adaptive" or any(
                    n.get("type") == "pending" or (n.get("attrs") or {}).get("generated")
                    for n in version.content.get("content") or []),
                proposals=sum(1 for v in s.versions if v.status == "proposed"),
                unlocked=s.unlocked, activation_override=s.activation_override,
                reviewed_by=s.reviewed_by, reviewed_at=s.reviewed_at,
                missing_data=version.missing_data, assumptions=version.assumptions,
                issues=version.issues,
                citations=[{"anchor": c.anchor, "kind": c.kind, "target": c.target_id}
                           for c in version.citations],
            ))  # fmt: skip
    return DocumentOut(
        id=d.id, project_id=d.project_id, type=d.type, origin=d.origin,
        source_file_id=d.source_file_id, status=d.status,
        revision_label=revision_label(d.revision), responsible_user_id=d.responsible_user_id,
        ficha_revision=revision.label if revision else "", created_at=d.created_at,
        counts=counts, sections=sections,
    )  # fmt: skip


APPROVED = "Peça aprovada: reabra-a para a alterar (cria a revisão seguinte)."


def ensure_editable(document: Document) -> None:
    """Every action that changes a section of an approved document is refused (Phase 6)."""
    if document.status == "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, APPROVED)


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    return document


@router.post("/projects/{project_id}/documents", status_code=status.HTTP_201_CREATED)
def assemble_document(
    project_id: uuid.UUID, body: AssembleIn, db: DB, user: Writer, settings: Config
) -> DocumentOut:
    project: Project = get_project(db, project_id)
    try:
        revision = confirmed_revision(db, project.id)
        profile = revision_profile(db, settings, revision) if revision else {}
        document = assemble(db, project, body.type, user.id, profile)
    except AssemblyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record(
        db, user, "document.assembled", "document", document.id,
        {"type": body.type, "sections": len(document.sections)}, project_id=project.id,
    )  # fmt: skip
    db.commit()
    return _out(db, document)


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: uuid.UUID, db: DB, _: CurrentUser) -> list[DocumentOut]:
    project = get_project(db, project_id)
    rows = db.scalars(
        select(Document)
        .where(Document.project_id == project.id)
        .order_by(Document.created_at.desc())
    )
    return [_out(db, d, with_sections=False) for d in rows]


@router.get("/documents/{document_id}")
def read_document(document_id: uuid.UUID, db: DB, _: CurrentUser) -> DocumentOut:
    return _out(db, get_document(db, document_id))


@router.get("/documents/{document_id}/export-check")
def export_check(document_id: uuid.UUID, db: DB, _: CurrentUser) -> dict[str, Any]:
    problems = export_readiness(db, get_document(db, document_id))
    return {"ready": not problems, "problems": problems}


@router.get("/documents/{document_id}/draft.docx")
def draft(document_id: uuid.UUID, db: DB, store: Store, user: Writer, settings: Config) -> Response:
    """The draft .docx: watermark "RASCUNHO — não aprovado" and never the official name."""
    from app.export import ExportRefused
    from app.export.docx import export_docx

    document = get_document(db, document_id)
    try:
        exported = export_docx(db, store, settings, document, official=False)
    except ExportRefused as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record(db, user, "document.draft_downloaded", "document", document.id, {"type": document.type},
           project_id=document.project_id)  # fmt: skip
    db.commit()
    name = exported.name
    return Response(exported.data, media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})  # fmt: skip
