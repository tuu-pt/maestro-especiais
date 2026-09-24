"""Ficha-base: read it, reveal personal values, resolve conflicts, confirm a revision."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.ingest.consolidate import latest_revision, open_conflict
from app.ingest.keys import GROUPS, KEYS
from app.models import FichaConflict, FichaRevision, FichaValue, ProjectFile
from app.validation.rules import cal_01

router = APIRouter(tags=["ficha-base"])

DB = Annotated[Session, Depends(get_session)]
Tecnico = Annotated[User, Depends(require_role("tecnico"))]

MASK = "•••"


class CandidateOut(BaseModel):
    value: Any
    source_type: str
    source_ref: str | None
    source_file: str | None  # file name, for the origin tooltip
    file_date: str | None


class ConflictOut(BaseModel):
    id: uuid.UUID
    candidates: list[CandidateOut]


class ValueOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    value: Any
    unit: str | None
    masked: bool
    personal_data: bool
    status: str
    source_type: str
    source_ref: str | None
    source_file: str | None
    conflict: ConflictOut | None


class GroupOut(BaseModel):
    name: str
    values: list[ValueOut]


class CircuitOut(BaseModel):
    id: uuid.UUID
    row_index: int
    section: str | None
    origin: str | None
    destination: str | None
    kva: Decimal | None
    ib_a: Decimal | None
    in_a: Decimal | None
    idn_ma: Decimal | None
    iz_a: Decimal | None
    i2_a: Decimal | None
    iz145_a: Decimal | None
    cable_raw: str | None
    length_m: Decimal | None
    vd_total_pct: Decimal | None
    breaking_capacity_ka: Decimal | None
    installation: str | None
    phases: int | None
    source_ref: str | None
    cal01: dict[str, str]


class RevisionOut(BaseModel):
    id: uuid.UUID
    label: str
    status: str
    confirmed_by: str | None
    confirmed_at: datetime | None
    created_at: datetime


class FichaOut(BaseModel):
    revision: RevisionOut | None
    revisions: list[RevisionOut]
    groups: list[GroupOut]
    circuits: list[CircuitOut]
    open_conflicts: int
    can_confirm: bool
    cal01_note: str


def _file_names(db: Session, ids: set[uuid.UUID]) -> dict[str, str]:
    if not ids:
        return {}
    rows = db.execute(select(ProjectFile.id, ProjectFile.filename).where(ProjectFile.id.in_(ids)))
    return {str(i): name for i, name in rows}


def _value_out(v: FichaValue, names: dict[str, str], reveal: bool = False) -> ValueOut:
    hide = v.personal_data and not reveal
    conflict = open_conflict(v)
    return ValueOut(
        id=v.id,
        key=v.key,
        label=v.label_pt,
        value=MASK if hide and v.value is not None else v.value,
        unit=v.unit,
        masked=hide and v.value is not None,
        personal_data=v.personal_data,
        status=v.status,
        source_type=v.source_type,
        source_ref=v.source_ref,
        source_file=names.get(str(v.source_file_id)) if v.source_file_id else None,
        conflict=ConflictOut(
            id=conflict.id,
            candidates=[
                CandidateOut(
                    value=MASK if hide else c["value"],
                    source_type=c["source_type"],
                    source_ref=c.get("source_ref"),
                    source_file=names.get(str(c.get("source_file_id"))),
                    file_date=c.get("file_date"),
                )
                for c in conflict.candidates
            ],
        )
        if conflict
        else None,
    )


def _names_for(db: Session, values: list[FichaValue]) -> dict[str, str]:
    ids: set[uuid.UUID] = {v.source_file_id for v in values if v.source_file_id}
    for v in values:
        conflict = open_conflict(v)
        for c in conflict.candidates if conflict else []:
            if c.get("source_file_id"):
                ids.add(uuid.UUID(c["source_file_id"]))
    return _file_names(db, ids)


@router.get("/projects/{project_id}/ficha")
def read_ficha(project_id: uuid.UUID, db: DB, _: CurrentUser) -> FichaOut:
    project = get_project(db, project_id)
    revisions = db.scalars(
        select(FichaRevision)
        .where(FichaRevision.project_id == project.id)
        .order_by(FichaRevision.created_at)
    ).all()
    current = latest_revision(db, project.id)
    order = {key: i for i, key in enumerate(KEYS)}  # the order of SPEC 7.2
    values = sorted(current.values if current else [], key=lambda v: order.get(v.key, len(order)))
    names = _names_for(db, values)
    groups = [
        GroupOut(name=g, values=[_value_out(v, names) for v in values if v.group == g])
        for g in GROUPS
    ]
    circuits = [
        CircuitOut.model_validate({**c.__dict__, "cal01": cal_01.check(c)})
        for c in (current.circuits if current else [])
    ]
    open_count = sum(1 for v in values if open_conflict(v))
    return FichaOut(
        revision=RevisionOut.model_validate(current, from_attributes=True) if current else None,
        revisions=[RevisionOut.model_validate(r, from_attributes=True) for r in revisions],
        groups=groups,
        circuits=circuits,
        open_conflicts=open_count,
        can_confirm=bool(current and current.status == "draft" and values and not open_count),
        cal01_note=cal_01.PENDING_NOTE,
    )


def _value(db: Session, value_id: uuid.UUID) -> FichaValue:
    value = db.get(FichaValue, value_id)
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Valor não encontrado.")
    return value


@router.post("/ficha/values/{value_id}/reveal")
def reveal(value_id: uuid.UUID, db: DB, user: CurrentUser) -> ValueOut:
    """The unmasked value. Every reveal is recorded (who, which key; never the value)."""
    value = _value(db, value_id)
    if value.personal_data:
        record(db, user, "ficha.value_revealed", "ficha_value", value.id, {"key": value.key},
               project_id=value.revision.project_id)  # fmt: skip
        db.commit()
    return _value_out(value, _names_for(db, [value]), reveal=True)


class ResolveIn(BaseModel):
    candidate: int | None = Field(default=None, ge=0, description="Index of the chosen candidate")
    manual_value: Any | None = None
    note: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def one_choice(self) -> "ResolveIn":
        if (self.candidate is None) == (self.manual_value is None):
            raise ValueError("Escolha um candidato ou indique um valor manual.")
        return self


@router.post("/ficha/conflicts/{conflict_id}/resolve")
def resolve(conflict_id: uuid.UUID, body: ResolveIn, db: DB, user: Tecnico) -> ValueOut:
    conflict = db.get(FichaConflict, conflict_id)
    if conflict is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conflito não encontrado.")
    if conflict.resolved_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este conflito já foi resolvido.")
    value = conflict.value
    if value is None:  # a circuit field (09-Folha): resolved with its own endpoint
        raise HTTPException(status.HTTP_409_CONFLICT, "Este conflito é de um troço.")
    if value.revision.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "A revisão já está confirmada.")
    if body.candidate is not None:
        if body.candidate >= len(conflict.candidates):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Candidato inexistente.")
        chosen = conflict.candidates[body.candidate]
        value.value = chosen["value"]
        value.source_type, value.source_ref = chosen["source_type"], chosen.get("source_ref")
        file_id = chosen.get("source_file_id")
        value.source_file_id = uuid.UUID(file_id) if file_id else None
        choice = {"choice": "candidate", "source_type": chosen["source_type"]}
    else:
        value.value = body.manual_value
        value.source_type, value.source_ref, value.source_file_id = "manual", None, None
        choice = {"choice": "manual"}
    value.status = "pending"
    conflict.resolved_value = value.value
    conflict.resolved_by = user.id
    conflict.resolved_at = datetime.now(UTC)
    conflict.note = body.note
    # The note is free text written by the técnico and may name people: it stays in the conflict.
    record(db, user, "ficha.conflict_resolved", "ficha_conflict", conflict.id,
           {"key": value.key, **choice}, project_id=value.revision.project_id)  # fmt: skip
    db.commit()
    return _value_out(value, _names_for(db, [value]))


@router.post("/ficha/revisions/{revision_id}/confirm")
def confirm(revision_id: uuid.UUID, db: DB, user: Tecnico) -> RevisionOut:
    revision = db.get(FichaRevision, revision_id)
    if revision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revisão não encontrada.")
    if revision.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta revisão já não está em rascunho.")
    if not revision.values:
        raise HTTPException(status.HTTP_409_CONFLICT, "A revisão ainda não tem valores.")
    if any(open_conflict(v) for v in revision.values):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Há conflitos por resolver: não é possível confirmar."
        )
    for previous in db.scalars(
        select(FichaRevision).where(
            FichaRevision.project_id == revision.project_id, FichaRevision.status == "confirmed"
        )
    ):
        previous.status = "superseded"
    for v in revision.values:
        v.status = "confirmed"
    revision.status = "confirmed"
    revision.confirmed_by = user.id
    revision.confirmed_at = datetime.now(UTC)
    record(db, user, "ficha.confirmed", "ficha_revision", revision.id,
           {"label": revision.label, "values": len(revision.values)},
           project_id=revision.project_id)  # fmt: skip
    db.commit()
    return RevisionOut.model_validate(revision, from_attributes=True)
