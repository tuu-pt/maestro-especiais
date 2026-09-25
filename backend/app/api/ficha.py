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
from app.ingest.base import to_number
from app.ingest.circuit_sheet import compare_sheet, drop_open_conflicts
from app.ingest.consolidate import latest_revision, open_conflict
from app.ingest.drawings import index_check
from app.ingest.keys import GROUPS, KEYS
from app.models import (
    BomItem,
    Circuit,
    CircuitSheet,
    FichaConflict,
    FichaRevision,
    FichaValue,
    ProjectFile,
)
from app.validation.rules import cal_01

router = APIRouter(tags=["ficha-base"])

DB = Annotated[Session, Depends(get_session)]
Tecnico = Annotated[User, Depends(require_role("tecnico"))]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]

# Circuit fields a 09-Folha is compared on, as the interface names them.
CIRCUIT_FIELD_LABELS = {
    "kva": "Potência", "ib_a": "IB", "in_a": "In", "iz_a": "Iz", "i2_a": "I2",
    "iz145_a": "1,45·Iz", "section_mm2": "Secção", "length_m": "Comprimento",
    "vd_section_pct": "Queda de tensão do troço",
}  # fmt: skip

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


class CircuitConflictOut(BaseModel):
    id: uuid.UUID
    field: str
    label: str
    candidates: list[CandidateOut]


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
    section_mm2: Decimal | None
    length_m: Decimal | None
    vd_section_pct: Decimal | None
    vd_total_pct: Decimal | None
    breaking_capacity_ka: Decimal | None
    installation: str | None
    phases: int | None
    source_ref: str | None
    cal01: dict[str, str]
    conflicts: list[CircuitConflictOut]


class CircuitSheetOut(BaseModel):
    """A 09-Folha: its values with their cells, and the circuit(s) it is linked to."""

    id: uuid.UUID
    origin_hint: str | None
    destination_hint: str | None
    source_file: str | None
    template: str
    values: dict[str, dict[str, Any]]
    circuit_ids: list[str]
    link_status: str


class BomItemOut(BaseModel):
    """One MQT/LPU line and the ficha key it is associated with."""

    id: uuid.UUID
    variant: str
    source_ref: str
    source_file: str | None
    code: str | None
    level: int
    kind: str
    designation: str | None
    unit: str | None
    quantity: Decimal | None
    link_key: str | None
    link_label: str | None
    link_status: str
    link_rule: str | None


class LinkKeyOut(BaseModel):
    key: str
    label: str
    group: str


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
    circuit_sheets: list[CircuitSheetOut]
    bom_items: list[BomItemOut]
    bom_link_keys: list[LinkKeyOut]
    # Index of the drawings vs the sheets of the PDF (case C4), when both were read.
    drawings_check: dict[str, Any] | None
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


def _open_circuit_conflicts(circuit: Circuit) -> list[FichaConflict]:
    return [c for c in circuit.conflicts if c.resolved_at is None]


def _circuit_out(c: Circuit, names: dict[str, str]) -> CircuitOut:
    conflicts = [
        CircuitConflictOut(
            id=k.id,
            field=k.field or "",
            label=CIRCUIT_FIELD_LABELS.get(k.field or "", k.field or ""),
            candidates=[
                CandidateOut(
                    value=x["value"],
                    source_type=x["source_type"],
                    source_ref=x.get("source_ref"),
                    source_file=names.get(str(x.get("source_file_id"))),
                    file_date=x.get("file_date"),
                )
                for x in k.candidates
            ],
        )
        for k in _open_circuit_conflicts(c)
    ]
    data = {**c.__dict__, "cal01": cal_01.check(c), "conflicts": conflicts}
    return CircuitOut.model_validate(data)


def _sheet_out(s: CircuitSheet, names: dict[str, str]) -> CircuitSheetOut:
    data = {**s.__dict__, "source_file": names.get(str(s.source_file_id))}
    return CircuitSheetOut.model_validate(data)


def _bom_out(i: BomItem, names: dict[str, str]) -> BomItemOut:
    key = KEYS.get(i.link_key or "")
    data = {
        **i.__dict__,
        "source_file": names.get(str(i.source_file_id)),
        "link_label": key.label_pt if key else None,
    }
    return BomItemOut.model_validate(data)


# Keys an MQT/LPU article can be associated with by hand (not personal, not identification).
BOM_LINK_KEYS = [
    LinkKeyOut(key=k, label=v.label_pt, group=v.group)
    for k, v in KEYS.items()
    if v.group in {"Distribuição", "Sistemas", "Equipamentos", "Alimentação"} and not v.personal
]


def _drawings_check(values: list[FichaValue]) -> dict[str, Any] | None:
    by_key = {v.key: v.value for v in values}
    index, sheets = by_key.get("pd.indice"), by_key.get("pd.folhas")
    if not isinstance(index, list) or not isinstance(sheets, list):
        return None
    return index_check(index, sheets, int(by_key.get("pd.n_paginas_pdf") or len(sheets)))


def _sheet_names(db: Session, revision: FichaRevision | None) -> dict[str, str]:
    if revision is None:
        return {}
    ids = {s.source_file_id for s in revision.circuit_sheets if s.source_file_id}
    ids |= {c.source_file_id for c in revision.circuits if c.source_file_id}
    ids |= {i.source_file_id for i in revision.bom_items if i.source_file_id}
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
    file_names = _sheet_names(db, current)
    circuits = [_circuit_out(c, file_names) for c in (current.circuits if current else [])]
    sheets = [_sheet_out(s, file_names) for s in (current.circuit_sheets if current else [])]
    open_count = sum(1 for v in values if open_conflict(v))
    open_count += sum(len(c.conflicts) for c in circuits)
    return FichaOut(
        revision=RevisionOut.model_validate(current, from_attributes=True) if current else None,
        revisions=[RevisionOut.model_validate(r, from_attributes=True) for r in revisions],
        groups=groups,
        circuits=circuits,
        circuit_sheets=sheets,
        bom_items=[_bom_out(i, file_names) for i in (current.bom_items if current else [])],
        bom_link_keys=BOM_LINK_KEYS,
        drawings_check=_drawings_check(values),
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


def _resolve_circuit(
    db: Session, conflict: FichaConflict, circuit: Circuit, body: ResolveIn, user: User
) -> CircuitOut:
    if circuit.revision.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "A revisão já está confirmada.")
    name = conflict.field or ""
    if body.candidate is not None:
        if body.candidate >= len(conflict.candidates):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Candidato inexistente.")
        chosen = conflict.candidates[body.candidate]
        number = to_number(chosen["value"])
        choice = {"choice": "candidate", "source_type": chosen["source_type"]}
    else:
        number = to_number(body.manual_value)
        if number is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Indique um número.")
        choice = {"choice": "manual"}
    setattr(circuit, name, number)  # chosen by a person; nothing is computed
    conflict.resolved_value = float(number) if number is not None else None
    conflict.resolved_by = user.id
    conflict.resolved_at = datetime.now(UTC)
    conflict.note = body.note
    where = f"{circuit.origin} → {circuit.destination}"
    record(db, user, "ficha.circuit_conflict_resolved", "ficha_conflict", conflict.id,
           {"field": name, "circuit": where, **choice},
           project_id=circuit.revision.project_id)  # fmt: skip
    db.commit()
    db.refresh(circuit)
    return _circuit_out(circuit, _sheet_names(db, circuit.revision))


@router.post("/ficha/conflicts/{conflict_id}/resolve")
def resolve(
    conflict_id: uuid.UUID, body: ResolveIn, db: DB, user: Tecnico
) -> ValueOut | CircuitOut:
    conflict = db.get(FichaConflict, conflict_id)
    if conflict is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conflito não encontrado.")
    if conflict.resolved_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este conflito já foi resolvido.")
    if conflict.circuit is not None:  # a circuit field (09-Folha)
        return _resolve_circuit(db, conflict, conflict.circuit, body, user)
    value = conflict.value
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conflito sem valor associado.")
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
    if any(open_conflict(v) for v in revision.values) or any(
        _open_circuit_conflicts(c) for c in revision.circuits
    ):
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


class LinkSheetIn(BaseModel):
    circuit_ids: list[uuid.UUID] = Field(description="One circuit, several equal ones, or none")


@router.post("/circuit-sheets/{sheet_id}/link")
def link_sheet(sheet_id: uuid.UUID, body: LinkSheetIn, db: DB, user: Writer) -> CircuitSheetOut:
    """A person links a 09-Folha to its circuit(s); the comparison runs again on them."""
    sheet = db.get(CircuitSheet, sheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "09-Folha não encontrada.")
    revision = sheet.revision
    if revision.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "A revisão já está confirmada.")
    circuits = {c.id: c for c in revision.circuits}
    wanted = list(dict.fromkeys(body.circuit_ids))
    if any(cid not in circuits for cid in wanted):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Troço inexistente nesta revisão."
        )
    drop_open_conflicts(db, sheet, revision)
    sheet.circuit_ids = [str(cid) for cid in wanted]
    sheet.link_status = "manual" if wanted else "unlinked"
    sheet.linked_by, sheet.linked_at = user.id, datetime.now(UTC)
    opened = sum(compare_sheet(db, sheet, circuits[cid]) for cid in wanted)
    label = f"{sheet.origin_hint or '?'}-{sheet.destination_hint or '?'}"
    record(db, user, "circuit_sheet.linked", "circuit_sheet", sheet.id,
           {"sheet": label, "circuits": len(wanted), "conflicts": opened},
           project_id=revision.project_id)  # fmt: skip
    db.commit()
    return _sheet_out(sheet, _sheet_names(db, revision))


class LinkBomIn(BaseModel):
    key: str | None = Field(description="Ficha key, or null to leave the article unlinked")


@router.post("/bom-items/{item_id}/link")
def link_bom_item(item_id: uuid.UUID, body: LinkBomIn, db: DB, user: Writer) -> BomItemOut:
    """A person associates an MQT/LPU article with a ficha key (or removes the association)."""
    item = db.get(BomItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artigo não encontrado.")
    if item.revision.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "A revisão já está confirmada.")
    if item.kind != "article":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só se associam artigos.")
    if body.key is not None and body.key not in {k.key for k in BOM_LINK_KEYS}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Chave da ficha inválida.")
    item.link_key = body.key
    item.link_status = "manual" if body.key else "unlinked"
    item.link_rule = None
    item.linked_by, item.linked_at = user.id, datetime.now(UTC)
    record(db, user, "bom_item.linked", "bom_item", item.id,
           {"code": item.code, "variant": item.variant, "link_key": body.key},
           project_id=item.revision.project_id)  # fmt: skip
    db.commit()
    names = _file_names(db, {item.source_file_id} if item.source_file_id else set())
    return _bom_out(item, names)
