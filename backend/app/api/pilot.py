"""The pilot (Phase 8): active time per step, the estimate of the manual process, problems."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.models import AuditEvent
from app.models.pilot import PilotBaseline, PilotNote, PilotTime
from app.pilot.metrics import pilot_projects, project_metrics
from app.pilot.steps import STEPS, step_for

router = APIRouter(tags=["piloto"])
DB = Annotated[Session, Depends(get_session)]
Estimator = Annotated[User, Depends(require_role("tecnico", "admin"))]
Triager = Annotated[User, Depends(require_role("admin", "curador"))]
HEARTBEAT_MAX_S = 60  # one heartbeat never adds more than this [A CONFIRMAR]


class HeartbeatIn(BaseModel):
    screen: str = Field(max_length=40)  # the route of the screen: ficha, documentos, revisao…
    hint: str | None = Field(default=None, max_length=20)  # inside a screen: mdj, cte, formularios
    seconds: int = Field(default=30, ge=1)


def reviewed(db: Session, project_id: uuid.UUID) -> bool:
    """The pieces of the project were sent for review at least once."""
    return bool(db.scalar(select(exists().where(
        AuditEvent.action == "review.requested",
        AuditEvent.payload["project_id"].astext == str(project_id)))))  # fmt: skip


@router.post("/projects/{project_id}/pilot/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(project_id: uuid.UUID, body: HeartbeatIn, db: DB, user: CurrentUser) -> Response:
    """Adds the active seconds to the step; a screen outside a project's work adds nothing.

    Not audited: one every 30 s would drown the history.
    """
    project = get_project(db, project_id)
    step = step_for(body.screen, body.hint, reviewed(db, project.id))
    if step is not None:
        seconds = min(body.seconds, HEARTBEAT_MAX_S)
        row = insert(PilotTime).values(
            id=uuid.uuid4(), project_id=project.id, user_id=user.id, step=step,
            day=datetime.now(UTC).date(), seconds=seconds,
        )  # fmt: skip
        added = {"seconds": PilotTime.seconds + seconds, "updated_at": datetime.now(UTC)}
        db.execute(row.on_conflict_do_update(constraint="uq_pilot_time", set_=added))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- estimate of the manual process


class BaselineIn(BaseModel):
    steps: dict[str, tuple[int, int]]  # step -> [min, max] minutes
    rounds: int | None = Field(default=None, ge=0, le=50)
    errors: str | None = Field(default=None, max_length=2000)
    typology: str | None = Field(default=None, max_length=120)

    @field_validator("steps")
    @classmethod
    def known_and_ordered(cls, steps: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
        unknown = sorted(set(steps) - set(STEPS))
        if unknown:
            raise ValueError(f"Passos desconhecidos: {', '.join(unknown)}.")
        for step, (low, high) in steps.items():
            if not 0 <= low <= high <= 100_000:
                raise ValueError(f"«{STEPS[step]}»: o mínimo tem de ser ≤ ao máximo (minutos).")
        return steps


class BaselineOut(BaseModel):
    steps: dict[str, list[int]]
    rounds: int | None
    errors: str | None
    typology: str | None
    updated_by: str | None
    updated_at: datetime | None


def baseline_out(b: PilotBaseline | None) -> BaselineOut | None:
    if b is None:
        return None
    return BaselineOut(steps=b.steps, rounds=b.rounds, errors=b.errors, typology=b.typology,
                       updated_by=b.updated_by, updated_at=b.updated_at)  # fmt: skip


@router.put("/projects/{project_id}/pilot/baseline")
def save_baseline(project_id: uuid.UUID, body: BaselineIn, db: DB, user: Estimator) -> BaselineOut:
    """The technician's estimate of the manual process, best written before the project starts."""
    project = get_project(db, project_id)
    row = db.scalars(select(PilotBaseline).where(PilotBaseline.project_id == project.id)).first()
    if row is None:
        row = PilotBaseline(id=uuid.uuid4(), project_id=project.id, created_by=user.id)
        db.add(row)
    row.steps = {k: list(v) for k, v in body.steps.items()}
    row.rounds, row.typology = body.rounds, (body.typology or "").strip() or None
    row.errors = (body.errors or "").strip() or None
    row.updated_by = user.id
    record(db, user, "pilot.baseline", "pilot_baseline", row.id,
           {"steps": sorted(body.steps)}, project_id=project.id)  # fmt: skip
    db.commit()
    db.refresh(row)
    out = baseline_out(row)
    assert out is not None
    return out


# ---------------------------------------------------------------- problems found during the pilot


class NoteIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    screen: str = Field(max_length=60)
    project_id: uuid.UUID | None = None
    hint: str | None = Field(default=None, max_length=20)


class NoteOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    screen: str
    step: str | None
    text: str
    status: str
    created_by: str | None
    created_at: datetime
    resolved_by: str | None
    resolved_at: datetime | None


def note_out(n: PilotNote) -> NoteOut:
    return NoteOut(id=n.id, project_id=n.project_id, screen=n.screen, step=n.step, text=n.text,
                   status=n.status, created_by=n.created_by, created_at=n.created_at,
                   resolved_by=n.resolved_by, resolved_at=n.resolved_at)  # fmt: skip


@router.post("/pilot/notes", status_code=status.HTTP_201_CREATED)
def add_note(body: NoteIn, db: DB, user: CurrentUser) -> NoteOut:
    """Anyone writes one; the text is theirs (the screen asks for no personal data)."""
    project = get_project(db, body.project_id) if body.project_id else None
    step = step_for(body.screen, body.hint, reviewed(db, project.id)) if project else None
    note = PilotNote(id=uuid.uuid4(), project_id=project.id if project else None,
                     screen=body.screen, step=step, text=body.text.strip(), status="open",
                     created_by=user.id)  # fmt: skip
    db.add(note)
    record(db, user, "pilot.note", "pilot_note", note.id, {"screen": body.screen, "step": step},
           project_id=project.id if project else None)  # fmt: skip
    db.commit()
    db.refresh(note)
    return note_out(note)


@router.get("/pilot/notes")
def list_notes(
    db: DB, _: CurrentUser, project: Annotated[uuid.UUID | None, Query()] = None
) -> list[NoteOut]:
    query = select(PilotNote).order_by(PilotNote.created_at.desc())
    if project is not None:
        query = query.where(PilotNote.project_id == project)
    return [note_out(n) for n in db.scalars(query)]


class NoteStatusIn(BaseModel):
    status: Literal["open", "resolved"]


@router.patch("/pilot/notes/{note_id}")
def set_note_status(note_id: uuid.UUID, body: NoteStatusIn, db: DB, user: Triager) -> NoteOut:
    note = db.get(PilotNote, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problema não encontrado.")
    note.status = body.status
    resolved = body.status == "resolved"
    note.resolved_by = user.id if resolved else None
    note.resolved_at = datetime.now(UTC) if resolved else None
    record(db, user, f"pilot.note_{body.status}", "pilot_note", note.id, {},
           project_id=note.project_id)  # fmt: skip
    db.commit()
    return note_out(note)


# ---------------------------------------------------------------- what the pilot measured


@router.get("/projects/{project_id}/pilot")
def project_pilot(project_id: uuid.UUID, db: DB, _: CurrentUser) -> dict[str, Any]:
    """Time per step against the estimate, incoherences at each approval, the goal, the notes."""
    project = get_project(db, project_id)
    baseline = db.scalars(select(PilotBaseline).where(PilotBaseline.project_id == project.id)
                          ).first()  # fmt: skip
    notes = db.scalars(select(PilotNote).where(PilotNote.project_id == project.id)
                       .order_by(PilotNote.created_at.desc())).all()  # fmt: skip
    return {**project_metrics(db, project).as_json(),
            "baseline": baseline_out(baseline), "notes": [note_out(n) for n in notes]}  # fmt: skip


@router.get("/pilot/summary")
def pilot_summary(db: DB, _: CurrentUser) -> list[dict[str, Any]]:
    """Every project of the pilot (time measured or an estimate written)."""
    return [project_metrics(db, p).as_json() for p in pilot_projects(db)]
