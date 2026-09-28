"""Validation (SPEC 9, screen E): run the rules, read the issues, ignore with a justification.

The validation only flags (P1): no endpoint here changes a piece. Ignoring an issue needs a
justification and goes to the audit log; the issue keeps its decision in the next runs.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.assembly.assemble import confirmed_revision
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.models import Document, ValidationIssue, ValidationRun
from app.validation.core import CATEGORIES
from app.validation.engine import NO_FICHA, latest, queue_run
from app.validation.jobs import ValidationQueue, get_validation_queue
from app.validation.rules import all_rules

router = APIRouter(tags=["validação"])

DB = Annotated[Session, Depends(get_session)]
Queue = Annotated[ValidationQueue, Depends(get_validation_queue)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]
UNAVAILABLE = "Não foi possível pôr a validação na fila: tente de novo dentro de momentos."


class RunIn(BaseModel):
    trigger: Literal["full", "changed"] = "full"


class IgnoreIn(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class ReopenIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class RunOut(BaseModel):
    id: uuid.UUID
    status: str
    trigger: str
    message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    totals: dict[str, Any]
    pieces: list[Any]


class IssueOut(BaseModel):
    id: uuid.UUID
    rule_id: str
    rule_title: str
    severity: str
    category: str
    category_label: str
    location: dict[str, Any]
    message: str
    evidence: dict[str, Any]
    likely_reading: str | None
    suggested_fix: str | None
    actions: list[Any]
    new: bool
    status: str
    ignored_reason: str | None
    resolved_by: str | None
    resolved_at: datetime | None


class ValidationOut(BaseModel):
    ready: bool  # a confirmed ficha-base exists
    current: RunOut | None  # the most recent run, whatever its state
    run: RunOut | None  # the last finished run: its issues and matrix are the ones shown
    issues: list[IssueOut]
    matrix: dict[str, Any]
    rules: list[dict[str, str]]


def _run_out(run: ValidationRun) -> RunOut:
    return RunOut(id=run.id, status=run.status, trigger=run.trigger, message=run.message,
                  created_at=run.created_at, started_at=run.started_at,
                  finished_at=run.finished_at, totals=run.totals, pieces=run.pieces)  # fmt: skip


def issue_out(i: ValidationIssue) -> IssueOut:
    titles = {r.id: r.title for r in all_rules()}
    return IssueOut(
        id=i.id, rule_id=i.rule_id, rule_title=titles.get(i.rule_id, i.rule_id),
        severity=i.severity, category=i.category,
        category_label=CATEGORIES.get(i.category, i.category), location=i.location,
        message=i.message_pt, evidence=i.evidence, likely_reading=i.likely_reading,
        suggested_fix=i.suggested_fix, actions=i.actions, new=i.new, status=i.status,
        ignored_reason=i.ignored_reason, resolved_by=i.resolved_by, resolved_at=i.resolved_at,
    )  # fmt: skip


def open_critical(db: Session, project_id: uuid.UUID) -> int:
    run = latest(db, project_id)
    if run is None:
        return 0
    return sum(1 for i in run.issues if i.severity == "critical" and i.status == "open")


@router.post("/projects/{project_id}/validation", status_code=status.HTTP_202_ACCEPTED)
def run_validation(project_id: uuid.UUID, body: RunIn, db: DB, queue: Queue, user: Writer
                   ) -> RunOut:  # fmt: skip
    project = get_project(db, project_id)
    if confirmed_revision(db, project.id) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_FICHA)
    run = queue_run(db, project, body.trigger, user.id)
    record(db, user, "validation.requested", "validation_run", run.id,
           {"trigger": body.trigger}, project_id=project.id)  # fmt: skip
    db.commit()
    if queue.enqueue(run.id) is None:
        run.status, run.message = "failed", UNAVAILABLE
        db.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE)
    return _run_out(run)


@router.get("/projects/{project_id}/validation")
def read_validation(
    project_id: uuid.UUID,
    db: DB,
    _: CurrentUser,
    severity: Annotated[list[str] | None, Query()] = None,
    rule: Annotated[list[str] | None, Query()] = None,
    piece: Annotated[str | None, Query()] = None,
    issue_status: Annotated[list[str] | None, Query(alias="status")] = None,
) -> ValidationOut:
    project = get_project(db, project_id)
    current = db.scalars(
        select(ValidationRun).where(ValidationRun.project_id == project.id)
        .order_by(ValidationRun.created_at.desc()).limit(1)
    ).first()  # fmt: skip
    done = latest(db, project.id)
    issues = list(done.issues) if done else []
    if severity:
        issues = [i for i in issues if i.severity in severity]
    if rule:
        issues = [i for i in issues if i.rule_id in rule]
    if piece:
        issues = [i for i in issues if (i.location or {}).get("piece") == piece]
    if issue_status:
        issues = [i for i in issues if i.status in issue_status]
    return ValidationOut(
        ready=confirmed_revision(db, project.id) is not None,
        current=_run_out(current) if current else None,
        run=_run_out(done) if done else None,
        issues=[issue_out(i) for i in issues],
        matrix=done.matrix if done else {},
        rules=rules_out(),
    )


def rules_out() -> list[dict[str, str]]:
    return [{"id": r.id, "title": r.title, "severity": r.severity,
             "category": CATEGORIES[r.category]} for r in all_rules()]  # fmt: skip


def _issue(db: Session, issue_id: uuid.UUID) -> ValidationIssue:
    issue = db.get(ValidationIssue, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta não encontrado.")
    return issue


@router.post("/validation/issues/{issue_id}/ignore")
def ignore(issue_id: uuid.UUID, body: IgnoreIn, db: DB, user: Writer) -> IssueOut:
    issue = _issue(db, issue_id)
    if issue.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só se ignora um alerta aberto.")
    issue.status, issue.ignored_reason = "ignored", body.reason.strip()
    issue.resolved_by, issue.resolved_at = user.id, datetime.now(UTC)
    record(db, user, "validation.issue_ignored", "validation_issue", issue.id,
           {"rule": issue.rule_id, "severity": issue.severity, "reason": issue.ignored_reason},
           project_id=issue.run.project_id)  # fmt: skip
    db.commit()
    return issue_out(issue)


@router.post("/validation/issues/{issue_id}/reopen")
def reopen(issue_id: uuid.UUID, body: ReopenIn, db: DB, user: Writer) -> IssueOut:
    issue = _issue(db, issue_id)
    if issue.status != "ignored":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só se reabre um alerta ignorado.")
    issue.status, issue.ignored_reason, issue.resolved_by, issue.resolved_at = (
        "open", None, None, None)  # fmt: skip
    record(
        db,
        user,
        "validation.issue_reopened",
        "validation_issue",
        issue.id,
        {"rule": issue.rule_id, "note": body.note},
        project_id=issue.run.project_id,
    )
    db.commit()
    return issue_out(issue)


class ReviewRequestIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


NOT_VALIDATED = "Valide o projeto antes de enviar as peças para revisão."
VALIDATING = "Há uma validação em curso: espere pelo resultado para enviar as peças para revisão."


@router.post("/projects/{project_id}/review-request")
def request_review(project_id: uuid.UUID, body: ReviewRequestIn, db: DB, user: Writer
                   ) -> dict[str, Any]:  # fmt: skip
    """Send the pieces for review (SPEC 10.E): refused while a critical issue is open."""
    project = get_project(db, project_id)
    current = db.scalars(
        select(ValidationRun).where(ValidationRun.project_id == project.id)
        .order_by(ValidationRun.created_at.desc()).limit(1)
    ).first()  # fmt: skip
    done = latest(db, project.id)
    if done is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_VALIDATED)
    if current is not None and current.status in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, VALIDATING)
    critical = [i for i in done.issues if i.severity == "critical" and i.status == "open"]
    if critical:
        n = len(critical)
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "message": f"{n} alerta{'s' if n > 1 else ''} crítico{'s' if n > 1 else ''} "
            f"abert{'os' if n > 1 else 'o'}: corrija-{'os' if n > 1 else 'o'} (ou ignore com "
            "justificação) antes de enviar as peças para revisão.",
            "open_critical": n,
        })  # fmt: skip
    documents = db.scalars(select(Document).where(Document.project_id == project.id)).all()
    if not documents:
        raise HTTPException(status.HTTP_409_CONFLICT, "Não há peças para enviar para revisão.")
    sent = [d for d in documents if d.status == "draft"]
    for d in sent:
        d.status = "in_review"
    record(db, user, "review.requested", "project", project.id,
           {"documents": len(sent), "run": str(done.id), "note": body.note},
           project_id=project.id)  # fmt: skip
    db.commit()
    return {"sent": len(sent), "documents": [str(d.id) for d in sent]}
