"""Documents of a project (SPEC 7.3, screen D): assemble, read, draft .docx, export check."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.assembly.assemble import AssemblyError, assemble, export_readiness
from app.assembly.docx import draft_docx
from app.assembly.values import ValueSource
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.models import Document, FichaRevision, Project
from app.storage import ObjectStore, get_store

router = APIRouter(tags=["documentos"])

DB = Annotated[Session, Depends(get_session)]
Store = Annotated[ObjectStore, Depends(get_store)]
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


class DocumentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    status: str
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
            ))  # fmt: skip
    return DocumentOut(
        id=d.id, project_id=d.project_id, type=d.type, status=d.status,
        ficha_revision=revision.label if revision else "", created_at=d.created_at,
        counts=counts, sections=sections,
    )  # fmt: skip


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    return document


@router.post("/projects/{project_id}/documents", status_code=status.HTTP_201_CREATED)
def assemble_document(project_id: uuid.UUID, body: AssembleIn, db: DB, user: Writer) -> DocumentOut:
    project: Project = get_project(db, project_id)
    try:
        document = assemble(db, project, body.type, user.id)
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
    problems = export_readiness(get_document(db, document_id))
    return {"ready": not problems, "problems": problems}


@router.get("/documents/{document_id}/draft.docx")
def draft(document_id: uuid.UUID, db: DB, store: Store, user: Writer) -> Response:
    document = get_document(db, document_id)
    revision = db.get(FichaRevision, document.ficha_revision_id)
    assert revision is not None
    try:
        data = draft_docx(db, store, document, ValueSource.load(db, revision))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    project = db.get(Project, document.project_id)
    record(db, user, "document.draft_downloaded", "document", document.id, {"type": document.type},
           project_id=document.project_id)  # fmt: skip
    db.commit()
    name = f"{project.code if project else 'PROJETO'}_{document.type}_rascunho.docx"
    return Response(data, media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})  # fmt: skip
