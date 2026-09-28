"""The validation run (SPEC 8.1 step 5, 9): read the pieces, run every rule, keep the issues.

- Reads again only the pieces whose content changed (PieceFacts); every rule runs every time,
  because a comparison between pieces may change when only one of them changed.
- An issue found again keeps its decision: ignored with a justification stays ignored (same
  fingerprint). An issue of the previous run that is not found again becomes "fixed".
- Progress goes to the project's SSE channel ("validation" events), without values.
- Nothing is corrected (P1): the run only writes ValidationRun and ValidationIssue.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.assemble import confirmed_revision
from app.audit import record
from app.config import Settings
from app.models import Project, ValidationIssue, ValidationRun
from app.profiles import revision_profile
from app.progress import Publish
from app.storage import ObjectStore
from app.validation.context import Context
from app.validation.core import Finding, Rule
from app.validation.extract import Sources, collect, read
from app.validation.matrix import build as build_matrix
from app.validation.rules import all_rules

logger = logging.getLogger(__name__)

NO_FICHA = "A validação fica disponível quando houver ficha-base confirmada e peças do projeto."
NO_PIECES = "Não há peças para validar: monte a MDJ e o CTE ou carregue as peças existentes."
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def event(run: ValidationRun, step: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"type": "validation", "run_id": str(run.id), "status": run.status,
            "message": run.message, "step": step, "totals": run.totals, **extra}  # fmt: skip


def latest(db: Session, project_id: uuid.UUID, *, before: ValidationRun | None = None
           ) -> ValidationRun | None:  # fmt: skip
    query = select(ValidationRun).where(
        ValidationRun.project_id == project_id, ValidationRun.status == "done"
    )
    if before is not None:
        query = query.where(ValidationRun.id != before.id)
    return db.scalars(query.order_by(ValidationRun.finished_at.desc()).limit(1)).first()


def validation_summary(db: Session, project_id: uuid.UUID) -> dict[str, Any] | None:
    """What the dashboard shows of the validation of a project, without opening it."""
    current = db.scalars(select(ValidationRun).where(ValidationRun.project_id == project_id)
                         .order_by(ValidationRun.created_at.desc()).limit(1)).first()  # fmt: skip
    if current is None:
        return None
    done = current if current.status == "done" else latest(db, project_id)
    open_issues = [i for i in done.issues if i.status == "open"] if done else []
    return {
        "status": current.status,
        "finished_at": done.finished_at.isoformat() if done and done.finished_at else None,
        "open_critical": sum(1 for i in open_issues if i.severity == "critical"),
        "new_critical": sum(1 for i in open_issues if i.severity == "critical" and i.new),
        "warning": sum(1 for i in open_issues if i.severity == "warning"),
    }


def queue_run(db: Session, project: Project, trigger: str, user_id: str | None) -> ValidationRun:
    # the clock, not now(): several runs may be queued in one transaction (tests, revalidation)
    run = ValidationRun(project_id=project.id, trigger=trigger, status="queued",
                        created_by=user_id, created_at=datetime.now(UTC))  # fmt: skip
    db.add(run)
    db.flush()
    return run


def _fail(db: Session, publish: Publish, run: ValidationRun, message: str) -> ValidationRun:
    run.status, run.message, run.finished_at = "failed", message, datetime.now(UTC)
    db.commit()
    publish(run.project_id, event(run))
    return run


def _check(rules: tuple[Rule, ...], ctx: Context) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    failed = []
    for rule in rules:
        try:
            findings += list(rule.check(ctx))
        except Exception as exc:  # noqa: BLE001 - one broken rule must not hide the others
            logger.error("validation rule failed: rule=%s error=%s", rule.id, type(exc).__name__)
            failed.append(rule.id)
    seen: set[str] = set()
    unique = []
    for f in findings:
        if f.fingerprint() not in seen:
            seen.add(f.fingerprint())
            unique.append(f)
    by_id = {r.id: r for r in rules}
    unique.sort(key=lambda f: (SEVERITY_ORDER[f.severity or by_id[f.rule_id].severity],
                               f.rule_id))  # fmt: skip
    return unique, failed


def _persist(db: Session, run: ValidationRun, rules: tuple[Rule, ...],
             findings: list[Finding]) -> list[ValidationIssue]:  # fmt: skip
    by_id = {r.id: r for r in rules}
    previous = latest(db, run.project_id, before=run)
    before = {i.fingerprint: i for i in previous.issues} if previous else {}
    issues = []
    for n, f in enumerate(findings):
        rule = by_id[f.rule_id]
        old = before.get(f.fingerprint())
        issue = ValidationIssue(
            run_id=run.id, order=n, rule_id=f.rule_id, severity=f.severity or rule.severity,
            category=rule.category, fingerprint=f.fingerprint(), location=f.location,
            message_pt=f.message, evidence=f.evidence, likely_reading=f.likely_reading,
            suggested_fix=f.suggested_fix, actions=f.actions, new=old is None, status="open",
        )  # fmt: skip
        if old is not None and old.status == "ignored":
            issue.status, issue.ignored_reason = "ignored", old.ignored_reason
            issue.resolved_by, issue.resolved_at = old.resolved_by, old.resolved_at
        db.add(issue)
        issues.append(issue)
    current = {i.fingerprint for i in issues}
    for old in before.values():
        if old.status == "open" and old.fingerprint not in current:
            old.status = "fixed"  # not found again: the piece was corrected
    return issues


def totals(issues: list[ValidationIssue]) -> dict[str, Any]:
    out: dict[str, Any] = {"critical": 0, "warning": 0, "info": 0, "open_critical": 0,
                           "new_critical": 0, "ignored": 0, "issues": len(issues)}  # fmt: skip
    for i in issues:
        out[i.severity] += 1
        if i.status == "ignored":
            out["ignored"] += 1
        if i.severity == "critical" and i.status == "open":
            out["open_critical"] += 1
            if i.new:
                out["new_critical"] += 1
    return out


def run_validation(db: Session, store: ObjectStore | None, settings: Settings,
                   publish: Publish, run_id: uuid.UUID) -> ValidationRun | None:  # fmt: skip
    run = db.get(ValidationRun, run_id)
    if run is None:
        logger.warning("validation: run %s no longer exists", run_id)
        return None
    project = db.get(Project, run.project_id)
    assert project is not None
    revision = confirmed_revision(db, project.id)
    if revision is None:
        return _fail(db, publish, run, NO_FICHA)
    run.status, run.started_at, run.ficha_revision_id = "running", datetime.now(UTC), revision.id
    db.commit()
    publish(project.id, event(run, "A ler as peças"))

    pieces = collect(db, project, revision)
    if not any(p.kind in ("MDJ", "CTE") for p in pieces):
        return _fail(db, publish, run, NO_PIECES)
    sources = Sources(db, store, revision, revision_profile(db, settings, revision))
    data = {}
    reread = 0
    for n, piece in enumerate(pieces, start=1):
        data[piece.ref], again = read(sources, project, piece)
        reread += again
        publish(project.id, event(run, f"A ler as peças ({n}/{len(pieces)})"))
    run.pieces = [p.as_json() for p in pieces]
    run.document_ids = [p.document_id for p in pieces if p.document_id]

    publish(project.id, event(run, "A correr as regras"))
    ctx = Context.load(db, project, revision, {p.ref: p for p in pieces}, data)
    ctx.memo["profile"] = sources.profile  # backend only: COE-04 compares with it
    rules = all_rules()
    findings, failed = _check(rules, ctx)
    issues = _persist(db, run, rules, findings)
    run.matrix = build_matrix(ctx, findings)
    run.totals = {**totals(issues), "pieces": len(pieces), "reread": reread,
                  "rules": len(rules), "rules_failed": failed}  # fmt: skip
    run.status, run.finished_at = "done", datetime.now(UTC)
    if failed:
        run.message = "Regras que não correram (ver registo): " + ", ".join(failed)
    record(db, None, "validation.run", "validation_run", run.id,
           {"trigger": run.trigger, **{k: v for k, v in run.totals.items() if k != "rules_failed"}},
           project_id=project.id)  # fmt: skip
    db.commit()
    publish(project.id, event(run))
    return run
