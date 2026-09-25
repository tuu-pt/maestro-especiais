"""Block library for the curator (SPEC 7.3, screen G): list, detail with evidence, preview.

Everyone reads it. Only a curator approves, rejects or edits a block, and every decision is
audited. Blocks never carry project or personal data: the evidence shown next to each paragraph
comes from the source sections, with the project's values as placeholders and personal data
masked.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.audit import AuditOut, _codes, _out
from app.api.projects import get_project
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.library.preview import label, preview
from app.library.rules import RuleError, parse
from app.models import AuditEvent, SourceSection, TemplateBlock

router = APIRouter(prefix="/library", tags=["biblioteca de blocos"])

DB = Annotated[Session, Depends(get_session)]
Curador = Annotated[User, Depends(require_role("curador"))]


class BlockSummary(BaseModel):
    id: uuid.UUID
    key: str
    doc_type: str
    kind: str
    level: int
    title: str
    order: int
    mode: str
    status: str
    activation_rule: str | None
    projects: list[str]
    required_keys: list[str]
    notes: list[str]
    version: int
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class EntryOut(BaseModel):
    mode: str
    project: str
    units: dict[str, list[int]]
    text: str | None
    keys: list[str]
    single_source: bool
    note: str | None


class EvidenceUnit(BaseModel):
    index: int
    kind: str
    text: str


class BlockDetail(BlockSummary):
    entries: list[EntryOut]
    evidence: dict[str, list[EvidenceUnit]]  # project -> elements of its source section
    labels: dict[str, str]  # placeholder key -> Portuguese label
    archive_refs: list[str]


class ParagraphOut(BaseModel):
    mode: str
    text: str | None
    missing: list[str]
    masked: list[str]


class PreviewOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    active: bool | None
    rule_error: str | None
    paragraphs: list[ParagraphOut]


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class EditIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    mode: Literal["fixed", "parametric", "adaptive"] | None = None
    activation_rule: str | None = Field(default=None, max_length=2000)
    note: str = Field(min_length=3, max_length=2000)  # why: it goes to the audit


def _summary(b: TemplateBlock) -> dict[str, Any]:
    return {
        "id": b.id, "key": b.key, "doc_type": b.doc_type, "kind": b.kind, "level": b.level,
        "title": b.title, "order": b.order, "mode": b.mode, "status": b.status,
        "activation_rule": b.activation_rule, "projects": b.projects,
        "required_keys": b.required_keys, "notes": b.notes, "version": b.version,
        "reviewed_by": b.reviewed_by, "reviewed_at": b.reviewed_at, "review_note": b.review_note,
    }  # fmt: skip


def _block(db: Session, block_id: uuid.UUID) -> TemplateBlock:
    block = db.get(TemplateBlock, block_id)
    if block is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloco não encontrado.")
    return block


@router.get("/blocks")
def list_blocks(
    db: DB, _: CurrentUser, doc_type: Annotated[Literal["MDJ", "CTE"] | None, Query()] = None
) -> list[BlockSummary]:
    query = select(TemplateBlock).order_by(TemplateBlock.doc_type.desc(), TemplateBlock.order)
    if doc_type:
        query = query.where(TemplateBlock.doc_type == doc_type)
    return [BlockSummary(**_summary(b)) for b in db.scalars(query)]


@router.get("/blocks/{block_id}")
def get_block(block_id: uuid.UUID, db: DB, _: CurrentUser) -> BlockDetail:
    b = _block(db, block_id)
    evidence: dict[str, list[EvidenceUnit]] = {}
    for ref in b.source_refs:
        section = (
            db.get(SourceSection, uuid.UUID(ref["section_id"])) if ref.get("section_id") else None
        )
        if section is not None:
            evidence[ref["project"]] = [
                EvidenceUnit(index=i, kind=u["kind"], text=u["text"])
                for i, u in enumerate(section.units)
            ]
    keys = {k for e in b.body_template for k in e.get("keys") or []} | set(b.required_keys)
    return BlockDetail(
        **_summary(b),
        entries=[EntryOut(mode=e["mode"], project=e["project"], units=e["units"], text=e["text"],
                          keys=e.get("keys") or [], single_source=bool(e.get("single_source")),
                          note=e.get("note")) for e in b.body_template],
        evidence=evidence,
        labels={k: label(k) for k in sorted(keys)},
        archive_refs=b.archive_refs,
    )  # fmt: skip


@router.get("/blocks/{block_id}/preview")
def preview_block(
    block_id: uuid.UUID, project_id: Annotated[uuid.UUID, Query()], db: DB, _: CurrentUser
) -> PreviewOut:
    b = _block(db, block_id)
    project = get_project(db, project_id)
    result = preview(db, b, project.id)
    return PreviewOut(
        project_id=project.id, project_code=project.code, active=result.active,
        rule_error=result.rule_error,
        paragraphs=[ParagraphOut(**vars(p)) for p in result.paragraphs],
    )  # fmt: skip


@router.post("/blocks/{block_id}/review")
def review_block(block_id: uuid.UUID, body: DecisionIn, db: DB, user: Curador) -> BlockSummary:
    b = _block(db, block_id)
    before = b.status
    b.status = body.decision
    b.reviewed_by, b.reviewed_at = user.id, datetime.now(UTC)
    b.review_note = (body.note or "").strip() or None
    record(
        db, user, f"library.block_{body.decision}", "template_block", b.id,
        {"key": b.key, "title": b.title, "doc_type": b.doc_type, "from": before},
        project_id=None,
    )  # fmt: skip
    db.commit()
    return BlockSummary(**_summary(b))


@router.patch("/blocks/{block_id}")
def edit_block(block_id: uuid.UUID, body: EditIn, db: DB, user: Curador) -> BlockSummary:
    """Title, mode or rule. An approved block that is edited goes back to "proposed"."""
    b = _block(db, block_id)
    changed: dict[str, Any] = {}
    if body.activation_rule is not None and body.activation_rule != b.activation_rule:
        try:
            tree = parse(body.activation_rule)
        except RuleError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                {"message": f"Regra inválida: {exc}", "position": exc.position},
            ) from exc
        changed["activation_rule"] = {"from": b.activation_rule, "to": body.activation_rule}
        b.activation_rule, b.activation_ast = body.activation_rule, tree
    if body.title is not None and body.title.strip() != b.title:
        changed["title"] = {"from": b.title, "to": body.title.strip()}
        b.title = body.title.strip()
    if body.mode is not None and body.mode != b.mode:
        changed["mode"] = {"from": b.mode, "to": body.mode}
        b.mode = body.mode
    if not changed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Não há alterações.")
    was = b.status
    if b.status != "proposed":
        b.status, b.reviewed_by, b.reviewed_at, b.review_note = "proposed", None, None, None
    record(
        db, user, "library.block_edited", "template_block", b.id,
        {"key": b.key, "title": b.title, "doc_type": b.doc_type, "changed": changed,
         "note": body.note.strip(), "from": was},
        project_id=None,
    )  # fmt: skip
    db.commit()
    return BlockSummary(**_summary(b))


@router.get("/blocks/{block_id}/history")
def block_history(block_id: uuid.UUID, db: DB, _: CurrentUser) -> list[AuditOut]:
    b = _block(db, block_id)
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "template_block", AuditEvent.entity_id == b.id)
        .order_by(AuditEvent.at, AuditEvent.id)
    ).all()
    codes = _codes(db)
    return [_out(e, codes) for e in events]
