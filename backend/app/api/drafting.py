"""Drafting with the LLM (SPEC 8.4, screen D): generate, requests in natural language, versions.

Every request to the LLM checks D5 first (Project.llm_allowed): while the terms of the Gemini
API are pending, only projects built from data/fixtures may use it, and only an admin turns it
on. The agent's text always arrives as a proposed version; a person accepts or rejects it.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import get_document
from app.api.projects import get_project
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.drafting.draft import accept, adaptive_entries, reject
from app.drafting.jobs import DraftQueue, get_draft_queue, to_draft
from app.models import Document, Project, Section, SectionVersion, TemplateBlock

router = APIRouter(tags=["redação"])

DB = Annotated[Session, Depends(get_session)]
Queue = Annotated[DraftQueue, Depends(get_draft_queue)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]
Admin = Annotated[User, Depends(require_role("admin"))]
INACTIVE = "A secção não está ativa: ative-a com justificação antes de a redigir."
D5 = "D5 pendente: este projeto não pode usar o LLM (só projetos criados a partir das fixtures)."


class RequestIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class LlmAllowedIn(BaseModel):
    allowed: bool
    reason: str = Field(min_length=3, max_length=2000)


class VersionOut(BaseModel):
    id: uuid.UUID
    number: int
    status: str
    author_type: str
    request: str | None
    missing_data: list[Any]
    assumptions: list[Any]
    issues: list[Any]
    created_at: datetime
    created_by: str | None
    content: dict[str, Any]
    citations: list[dict[str, Any]]


def _version_out(v: SectionVersion) -> VersionOut:
    return VersionOut(
        id=v.id, number=v.number, status=v.status, author_type=v.author_type, request=v.request,
        missing_data=v.missing_data, assumptions=v.assumptions, issues=v.issues,
        created_at=v.created_at, created_by=v.created_by, content=v.content,
        citations=[{"anchor": c.anchor, "kind": c.kind, "target": c.target_id}
                   for c in v.citations],
    )  # fmt: skip


def _section(db: Session, section_id: uuid.UUID) -> Section:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secção não encontrada.")
    return section


def _allowed(db: Session, document: Document, user: User) -> Project:
    project = db.get(Project, document.project_id)
    assert project is not None
    if not project.llm_allowed:
        record(db, user, "llm.refused", "project", project.id, {"reason": "D5"},
               project_id=project.id)  # fmt: skip
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, D5)
    return project


def _queued(job: str | None) -> None:
    if job is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "A fila de redação não está disponível: tente mais tarde.")  # fmt: skip


@router.post("/documents/{document_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_document(document_id: uuid.UUID, db: DB, queue: Queue, user: Writer) -> dict[str, Any]:
    document = get_document(db, document_id)
    project = _allowed(db, document, user)
    sections = to_draft(db, document)
    record(db, user, "document.generation_requested", "document", document.id,
           {"type": document.type, "sections": len(sections)}, project_id=project.id)  # fmt: skip
    db.commit()
    _queued(queue.document(document.id))
    return {"queued": len(sections)}


@router.post("/sections/{section_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_section(section_id: uuid.UUID, db: DB, queue: Queue, user: Writer) -> dict[str, Any]:
    return _enqueue_section(db, queue, user, _section(db, section_id), None)


@router.post("/sections/{section_id}/requests", status_code=status.HTTP_202_ACCEPTED)
def request_section(
    section_id: uuid.UUID, body: RequestIn, db: DB, queue: Queue, user: Writer
) -> dict[str, Any]:
    return _enqueue_section(db, queue, user, _section(db, section_id), body.text.strip())


def _enqueue_section(db: Session, queue: DraftQueue, user: User, section: Section,
                     request: str | None) -> dict[str, Any]:  # fmt: skip
    block = db.get(TemplateBlock, section.block_id) if section.block_id else None
    if block is None or not adaptive_entries(block):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Os blocos fixos e paramétricos não passam pelo LLM.")  # fmt: skip
    if not section.active:
        raise HTTPException(status.HTTP_409_CONFLICT, INACTIVE)
    project = _allowed(db, section.document, user)
    record(db, user, "section.request" if request else "section.generation_requested", "section",
           section.id, {"title": section.title, "has_request": bool(request)},
           project_id=project.id)  # fmt: skip
    db.commit()
    _queued(queue.section(section.id, request))
    return {"queued": 1}


@router.get("/sections/{section_id}/versions")
def versions(section_id: uuid.UUID, db: DB, _: CurrentUser) -> list[VersionOut]:
    return [_version_out(v) for v in _section(db, section_id).versions]


def _version(db: Session, version_id: uuid.UUID) -> SectionVersion:
    version = db.get(SectionVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Versão não encontrada.")
    if version.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta versão já não é uma proposta.")
    return version


@router.post("/versions/{version_id}/accept")
def accept_version(version_id: uuid.UUID, body: DecisionIn, db: DB, user: Writer) -> VersionOut:
    version = _version(db, version_id)
    section = accept(db, version, user.id)
    record(db, user, "section.version_accepted", "section", section.id,
           {"title": section.title, "version": version.number, "note": body.note},
           project_id=section.document.project_id)  # fmt: skip
    db.commit()
    return _version_out(version)


@router.post("/versions/{version_id}/reject")
def reject_version(version_id: uuid.UUID, body: DecisionIn, db: DB, user: Writer) -> VersionOut:
    version = _version(db, version_id)
    section = reject(db, version)
    record(db, user, "section.version_rejected", "section", section.id,
           {"title": section.title, "version": version.number, "note": body.note},
           project_id=section.document.project_id)  # fmt: skip
    db.commit()
    return _version_out(version)


@router.patch("/projects/{project_id}/llm")
def set_llm_allowed(
    project_id: uuid.UUID, body: LlmAllowedIn, db: DB, user: Admin
) -> dict[str, Any]:
    """D5: only an admin lets a project use the LLM (while pending, only fixture projects)."""
    project = get_project(db, project_id)
    project.llm_allowed = body.allowed
    record(db, user, "project.llm_allowed", "project", project.id,
           {"allowed": body.allowed, "reason": body.reason.strip()},
           project_id=project.id)  # fmt: skip
    db.commit()
    return {"llm_allowed": project.llm_allowed}
