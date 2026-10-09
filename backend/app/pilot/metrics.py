"""What the pilot measures (Phase 8, SPEC 1 and 14), per project.

- Time in the application per step (the heartbeats), against the technician's estimate of the
  manual process (minimum and maximum minutes per step). The reduction is measured against the
  middle of the estimate; the SPEC goal is on the MDJ, the CTE and the forms (≥ 40 %).
- Incoherences at each approval: the last finished validation before the piece was approved, for
  the three groups of the goal (identification COE-04, power COE-05, cables COE-06): how many
  were found while the project was made (distinct fingerprints up to then), and how many were
  still open or ignored when it was approved. The issues have no link to a piece, so the count is
  of the project [A CONFIRMAR].
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentRevision,
    PilotBaseline,
    PilotNote,
    PilotTime,
    Project,
    ValidationIssue,
    ValidationRun,
)
from app.pilot.steps import GOAL_STEPS, STEPS
from app.review import revision_label

GROUPS = {"identificacao": ("COE-04", "Identificação"), "potencia": ("COE-05", "Potência"),
          "cabos": ("COE-06", "Cabos")}  # fmt: skip
GOAL_REDUCTION = 0.40


@dataclass
class StepRow:
    step: str
    label: str
    seconds: int
    estimate: tuple[int, int] | None  # minutes

    def as_json(self) -> dict[str, Any]:
        return {"step": self.step, "label": self.label, "seconds": self.seconds,
                "estimate_min": list(self.estimate) if self.estimate else None}  # fmt: skip


@dataclass
class Approval:
    document: str
    revision: str
    approved_at: datetime
    groups: dict[str, dict[str, int]]  # group -> found, open, ignored

    @property
    def clean(self) -> bool:
        return all(g["open"] + g["ignored"] == 0 for g in self.groups.values())

    def as_json(self) -> dict[str, Any]:
        return {"document": self.document, "revision": self.revision,
                "approved_at": self.approved_at.isoformat(), "groups": self.groups,
                "clean": self.clean}  # fmt: skip


@dataclass
class ProjectMetrics:
    project_id: uuid.UUID
    code: str
    typology: str | None
    steps: list[StepRow]
    rounds_estimate: int | None
    errors_estimate: str | None
    has_estimate: bool
    approvals: list[Approval] = field(default_factory=list)
    notes_open: int = 0
    notes_total: int = 0

    def _sum(self, steps: tuple[str, ...] | None = None) -> tuple[int, float | None]:
        rows = [r for r in self.steps if steps is None or r.step in steps]
        app = sum(r.seconds for r in rows)
        estimated = [r for r in rows if r.estimate]
        middle = sum((r.estimate[0] + r.estimate[1]) / 2 for r in estimated if r.estimate)
        return app, (middle * 60 if estimated else None)

    def reduction(self, steps: tuple[str, ...] | None = None) -> float | None:
        """1 - time in the application / middle of the estimate, on the steps with an estimate."""
        rows = [r for r in self.steps if (steps is None or r.step in steps) and r.estimate]
        if not rows:
            return None
        app = sum(r.seconds for r in rows)
        middle = sum((r.estimate[0] + r.estimate[1]) / 2 * 60 for r in rows if r.estimate)
        return None if middle == 0 else 1 - app / middle

    @property
    def goal(self) -> dict[str, Any]:
        reduction = self.reduction(GOAL_STEPS)
        time_ok = reduction is not None and reduction >= GOAL_REDUCTION
        coherent = bool(self.approvals) and all(a.clean for a in self.approvals)
        return {"reduction": reduction, "time_ok": time_ok, "approved": bool(self.approvals),
                "coherent": coherent, "met": time_ok and coherent}  # fmt: skip

    def as_json(self) -> dict[str, Any]:
        app_total, estimate_total = self._sum()
        return {
            "project_id": str(self.project_id), "code": self.code, "typology": self.typology,
            "steps": [r.as_json() for r in self.steps], "seconds": app_total,
            "estimate_seconds": estimate_total, "reduction": self.reduction(),
            "has_estimate": self.has_estimate, "rounds_estimate": self.rounds_estimate,
            "errors_estimate": self.errors_estimate,
            "approvals": [a.as_json() for a in self.approvals], "goal": self.goal,
            "notes_open": self.notes_open, "notes_total": self.notes_total,
        }  # fmt: skip


def _approval(db: Session, project_id: uuid.UUID, doc: Document, rev: DocumentRevision,
              ) -> Approval:  # fmt: skip
    runs = select(ValidationRun.id).where(
        ValidationRun.project_id == project_id, ValidationRun.status == "done",
        ValidationRun.finished_at <= rev.approved_at)  # fmt: skip
    last = db.scalars(runs.order_by(ValidationRun.finished_at.desc()).limit(1)).first()
    groups: dict[str, dict[str, int]] = {}
    for group, (rule, _label) in GROUPS.items():
        found = db.scalar(select(func.count(func.distinct(ValidationIssue.fingerprint))).where(
            ValidationIssue.run_id.in_(runs), ValidationIssue.rule_id == rule))  # fmt: skip
        at_approval = db.scalars(select(ValidationIssue).where(
            ValidationIssue.run_id == last, ValidationIssue.rule_id == rule)).all()  # fmt: skip
        groups[group] = {
            "found": found or 0,
            "open": sum(1 for i in at_approval if i.status == "open"),
            "ignored": sum(1 for i in at_approval if i.status == "ignored"),
        }
    return Approval(doc.type, revision_label(rev.number), rev.approved_at, groups)


def project_metrics(db: Session, project: Project) -> ProjectMetrics:
    seconds: dict[str, int] = {
        step: int(total) for step, total in db.execute(
            select(PilotTime.step, func.sum(PilotTime.seconds))
            .where(PilotTime.project_id == project.id).group_by(PilotTime.step))
    }  # fmt: skip
    baseline = db.scalars(select(PilotBaseline).where(PilotBaseline.project_id == project.id)
                          ).first()  # fmt: skip
    estimates = baseline.steps if baseline else {}
    rows = [StepRow(step, label, seconds.get(step, 0),
                    (estimates[step][0], estimates[step][1]) if step in estimates else None)
            for step, label in STEPS.items()]  # fmt: skip
    revisions = db.execute(
        select(Document, DocumentRevision).join(DocumentRevision)
        .where(Document.project_id == project.id, Document.origin == "assembled")
        .order_by(DocumentRevision.approved_at)).all()  # fmt: skip
    notes = db.scalars(select(PilotNote).where(PilotNote.project_id == project.id)).all()
    return ProjectMetrics(
        project_id=project.id, code=project.code,
        typology=(baseline.typology if baseline and baseline.typology else project.building_type),
        steps=rows, rounds_estimate=baseline.rounds if baseline else None,
        errors_estimate=baseline.errors if baseline else None, has_estimate=bool(estimates),
        approvals=[_approval(db, project.id, d, r) for d, r in revisions],
        notes_open=sum(1 for n in notes if n.status == "open"), notes_total=len(notes),
    )  # fmt: skip


def pilot_projects(db: Session) -> list[Project]:
    """The projects of the pilot: those with time measured or an estimate written."""
    ids = set(db.scalars(select(PilotTime.project_id).distinct()))
    ids |= set(db.scalars(select(PilotBaseline.project_id)))
    if not ids:
        return []
    return list(db.scalars(select(Project).where(Project.id.in_(ids)).order_by(Project.code)))
