"""Approval of a document by its técnico responsável (SPEC 4, P6, 10.H; Phase 6).

draft → in_review (the review request of Phase 5) → approved (here, only by the técnico
assigned, with every condition met) → reopened as the next revision (draft again).
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.documents import ensure_editable, get_document
from app.audit import record
from app.auth import DEV_USERS, CurrentUser, User, require_role
from app.db import get_session
from app.models import Document, DocumentRevision
from app.review import (
    conditions,
    file_version,
    header_revision,
    ready,
    revision_label,
    section_snapshot,
)

router = APIRouter(tags=["revisão"])
DB = Annotated[Session, Depends(get_session)]
Tecnico = Annotated[User, Depends(require_role("tecnico"))]
Assigner = Annotated[User, Depends(require_role("tecnico", "admin"))]

# "JUNHO/2026", "junho de 2026", "06/2026": what a técnico writes in the header (P8: optional)
HEADER_DATE = re.compile(
    r"^\s*(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro"
    r"|dezembro|0?[1-9]|1[0-2])\s*(de|/|\|)?\s*\d{4}\s*$", re.I,
)  # fmt: skip


def user_name(user_id: str | None) -> str | None:
    if not user_id:
        return None
    return next((u.name for u in DEV_USERS.values() if u.id == user_id), user_id)


def tecnicos() -> list[User]:
    """Who may be assigned (development users until D6; then the directory)."""
    return [u for u in DEV_USERS.values() if "tecnico" in u.roles]


class RevisionOut(BaseModel):
    number: int
    label: str
    file_version: str
    header_revision: str
    approved_by: str
    approved_by_name: str | None
    approved_at: datetime
    header_date: str | None
    sections: int
    reopened_by_name: str | None
    reopened_at: datetime | None
    reopen_reason: str | None


class ApprovalOut(BaseModel):
    document_id: uuid.UUID
    type: str
    status: str
    origin: str
    revision: int
    revision_label: str
    file_version: str
    header_revision: str
    header_date: str | None
    responsible_id: str | None
    responsible_name: str | None
    approved_by_name: str | None
    approved_at: datetime | None
    conditions: list[dict[str, Any]]
    ready: bool
    can_approve: bool  # for the user asking: assigned, in review and every condition met
    why_not: str | None  # why this user cannot approve, when they cannot
    revisions: list[RevisionOut]
    tecnicos: list[dict[str, str]]


def _revision_out(r: DocumentRevision) -> RevisionOut:
    return RevisionOut(
        number=r.number, label=revision_label(r.number), file_version=file_version(r.number),
        header_revision=header_revision(r.number), approved_by=r.approved_by,
        approved_by_name=user_name(r.approved_by), approved_at=r.approved_at,
        header_date=r.header_date, sections=len(r.sections),
        reopened_by_name=user_name(r.reopened_by), reopened_at=r.reopened_at,
        reopen_reason=r.reopen_reason,
    )  # fmt: skip


def why_not(document: Document, user: User, is_ready: bool) -> str | None:
    if document.status == "approved":
        return "A peça já está aprovada."
    if "tecnico" not in user.roles:
        return "Só um técnico responsável aprova peças."
    if document.responsible_user_id != user.id:
        return f"Só o técnico atribuído ({user_name(document.responsible_user_id) or '—'}) aprova."
    if document.status != "in_review":
        return "A peça ainda não foi enviada para revisão (ecrã de validação)."
    if not is_ready:
        return "Há condições por cumprir."
    return None


def approval_out(db: Session, document: Document, user: User) -> ApprovalOut:
    found = conditions(db, document)
    is_ready = ready(found)
    reason = why_not(document, user, is_ready)
    n = document.revision
    return ApprovalOut(
        document_id=document.id, type=document.type, status=document.status,
        origin=document.origin, revision=n, revision_label=revision_label(n),
        file_version=file_version(n), header_revision=header_revision(n),
        header_date=document.header_date, responsible_id=document.responsible_user_id,
        responsible_name=user_name(document.responsible_user_id),
        approved_by_name=user_name(document.approved_by), approved_at=document.approved_at,
        conditions=[c.as_json() for c in found], ready=is_ready, can_approve=reason is None,
        why_not=reason, revisions=[_revision_out(r) for r in document.revisions],
        tecnicos=[{"id": u.id, "name": u.name} for u in tecnicos()],
    )  # fmt: skip


@router.get("/documents/{document_id}/approval")
def read_approval(document_id: uuid.UUID, db: DB, user: CurrentUser) -> ApprovalOut:
    return approval_out(db, get_document(db, document_id), user)


class ResponsibleIn(BaseModel):
    user_id: str
    reason: str = Field(min_length=10, max_length=2000)


@router.patch("/documents/{document_id}/responsible")
def assign(document_id: uuid.UUID, body: ResponsibleIn, db: DB, user: Assigner) -> ApprovalOut:
    document = get_document(db, document_id)
    ensure_editable(document)
    if body.user_id not in {u.id for u in tecnicos()}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Só um utilizador com o papel técnico pode ser responsável.",
        )
    before = document.responsible_user_id
    document.responsible_user_id = body.user_id
    record(db, user, "document.responsible_assigned", "document", document.id,
           {"type": document.type, "from": before, "to": body.user_id,
            "reason": body.reason.strip()}, project_id=document.project_id)  # fmt: skip
    db.commit()
    return approval_out(db, document, user)


class HeaderIn(BaseModel):
    header_date: str | None = Field(default=None, max_length=30)


@router.patch("/documents/{document_id}/header")
def set_header(document_id: uuid.UUID, body: HeaderIn, db: DB, user: Tecnico) -> ApprovalOut:
    """The month/year of the header: only the técnico writes it (P8); empty by default."""
    document = get_document(db, document_id)
    ensure_editable(document)
    value = (body.header_date or "").strip() or None
    if value is not None and not HEADER_DATE.match(value):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Escreva o mês e o ano, por exemplo «JUNHO/2026».")  # fmt: skip
    document.header_date = value.upper() if value else None
    payload = {"type": document.type, "set": value is not None}
    record(db, user, "document.header_date", "document", document.id, payload,
           project_id=document.project_id)  # fmt: skip
    db.commit()
    return approval_out(db, document, user)


@router.post("/documents/{document_id}/approve")
def approve(document_id: uuid.UUID, db: DB, user: Tecnico) -> ApprovalOut:
    document = get_document(db, document_id)
    found = conditions(db, document)
    reason = why_not(document, user, ready(found))
    if reason is not None:
        failing = [c.as_json() for c in found if not c.ok]
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": reason, "conditions": failing})
    now = datetime.now(UTC)
    document.status, document.approved_by, document.approved_at = "approved", user.id, now
    db.add(DocumentRevision(
        document_id=document.id, number=document.revision, approved_by=user.id, approved_at=now,
        ficha_revision_id=document.ficha_revision_id, header_date=document.header_date,
        sections=section_snapshot(document), created_by=user.id,
    ))  # fmt: skip
    record(db, user, "document.approved", "document", document.id,
           {"type": document.type, "revision": revision_label(document.revision)},
           project_id=document.project_id)  # fmt: skip
    db.commit()
    db.refresh(document)
    return approval_out(db, document, user)


class ReopenIn(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


@router.post("/documents/{document_id}/reopen")
def reopen(document_id: uuid.UUID, body: ReopenIn, db: DB, user: Tecnico) -> ApprovalOut:
    """An approved document opens as the next revision (V0 → V1, rev. A → B), in draft.

    Sections stay reviewed until they change: an edit, an accepted proposal or a new assembly
    asks for a new review (as before the approval).
    """
    document = get_document(db, document_id)
    if document.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só se reabre uma peça aprovada.")
    approved = next(r for r in document.revisions if r.number == document.revision)
    now = datetime.now(UTC)
    approved.reopened_by, approved.reopened_at = user.id, now
    approved.reopen_reason = body.reason.strip()
    document.revision += 1
    document.status, document.approved_by, document.approved_at = "draft", None, None
    record(db, user, "document.reopened", "document", document.id,
           {"type": document.type, "from": revision_label(approved.number),
            "to": revision_label(document.revision), "reason": body.reason.strip()},
           project_id=document.project_id)  # fmt: skip
    db.commit()
    db.refresh(document)
    return approval_out(db, document, user)
