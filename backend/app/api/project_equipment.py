"""Equipment of a project (screen F): one row per slot of the latest assembled CTE (Phase 7).

Everyone reads it; the redator and the técnico choose an item of the library for a slot (with a
reason when it is not the reference one). The choice is audited and brings the item's
illustration into the .docx. An approved CTE is not changed (reopen it first).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.documents import ensure_editable
from app.api.equipment import CheckOut, DatasheetOut, _check_out, _sheet
from app.api.projects import get_project
from app.assembly.assemble import confirmed_revision
from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.equipment import CATEGORIES
from app.equipment.datasheets import current
from app.equipment.project import SlotView, alternatives, latest_cte, quantity, view
from app.models import Document, Equipment, ProjectEquipment, Section

router = APIRouter(tags=["equipamentos do projeto"])

DB = Annotated[Session, Depends(get_session)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]


class ItemOut(BaseModel):
    id: uuid.UUID
    category: str
    category_label: str
    name: str
    manufacturer: str
    model: str | None
    reference: str | None
    code: str | None
    status: str
    datasheet: DatasheetOut | None
    has_image: bool


class SlotOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    section_id: uuid.UUID
    section_title: str
    entry: int
    block_key: str
    item: ItemOut | None
    is_reference: bool  # the item of the reference project
    chosen: bool  # a person chose or confirmed it (its illustration goes into the .docx)
    chosen_by: str | None
    chosen_at: datetime | None
    reason: str | None
    or_equivalent: bool
    ficha_key: str | None
    quantity: Decimal | None
    unit: str | None
    articles: list[str]
    verdict: str
    checks: list[CheckOut]


class AlternativeOut(BaseModel):
    item: ItemOut
    verdict: str
    checks: list[CheckOut]


class SlotDetail(SlotOut):
    alternatives: list[AlternativeOut]


class ProjectEquipmentOut(BaseModel):
    document_id: uuid.UUID | None
    document_status: str | None
    slots: list[SlotOut]


class ChooseIn(BaseModel):
    equipment_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=2000)


def _item(e: Equipment) -> ItemOut:
    sheet = current(e)
    label = CATEGORIES.get(e.category, e.category)
    return ItemOut(id=e.id, category=e.category, category_label=label,
                   name=e.name, manufacturer=e.manufacturer, model=e.model, reference=e.reference,
                   code=e.code, status=e.status, datasheet=_sheet(sheet) if sheet else None,
                   has_image=bool(e.image))  # fmt: skip


def _slot(db: Session, v: SlotView, revision_id: Any) -> dict[str, Any]:
    pe = v.slot
    section = db.get(Section, pe.section_id)
    q = quantity(db, revision_id, pe, v.item) if v.item and revision_id else None
    return {
        "id": pe.id, "document_id": pe.document_id, "section_id": pe.section_id,
        "section_title": section.title if section else "", "entry": pe.entry,
        "block_key": pe.block_key, "item": _item(v.item) if v.item else None,
        "is_reference": pe.equipment_id == pe.default_equipment_id,
        "chosen": pe.chosen_by is not None, "chosen_by": pe.chosen_by, "chosen_at": pe.chosen_at,
        "reason": pe.reason, "or_equivalent": pe.or_equivalent, "ficha_key": pe.ficha_key,
        "quantity": q.value if q else None, "unit": q.unit if q else None,
        "articles": q.articles if q else [], "verdict": v.verdict,
        "checks": [_check_out(c) for c in v.checks],
    }  # fmt: skip


def _get(db: Session, slot_id: uuid.UUID) -> ProjectEquipment:
    pe = db.get(ProjectEquipment, slot_id)
    if pe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipamento do projeto não encontrado.")
    return pe


def _detail(db: Session, pe: ProjectEquipment) -> SlotDetail:
    document = db.get(Document, pe.document_id)
    revision_id = document.ficha_revision_id if document else None
    return SlotDetail(
        **_slot(db, view(db, pe), revision_id),
        alternatives=[AlternativeOut(item=_item(a.item), verdict=a.verdict,
                                     checks=[_check_out(c) for c in a.checks])
                      for a in alternatives(db, pe) if a.item is not None],
    )  # fmt: skip


@router.get("/projects/{project_id}/equipment")
def project_equipment(project_id: uuid.UUID, db: DB, _: CurrentUser) -> ProjectEquipmentOut:
    project = get_project(db, project_id)
    document = latest_cte(db, project.id)
    if document is None:
        return ProjectEquipmentOut(document_id=None, document_status=None, slots=[])
    revision = confirmed_revision(db, project.id)
    rows = db.scalars(select(ProjectEquipment).where(ProjectEquipment.document_id == document.id)
                      .order_by(ProjectEquipment.created_at, ProjectEquipment.entry,
                                ProjectEquipment.slot)).all()  # fmt: skip
    order = {s.id: s.order for s in document.sections}
    rows = sorted(rows, key=lambda r: (order.get(r.section_id, 0), r.entry, r.slot))
    return ProjectEquipmentOut(
        document_id=document.id, document_status=document.status,
        slots=[SlotOut(**_slot(db, view(db, pe), revision.id if revision else None))
               for pe in rows],
    )  # fmt: skip


@router.get("/project-equipment/{slot_id}")
def slot_detail(slot_id: uuid.UUID, db: DB, _: CurrentUser) -> SlotDetail:
    return _detail(db, _get(db, slot_id))


@router.put("/project-equipment/{slot_id}")
def choose(slot_id: uuid.UUID, body: ChooseIn, db: DB, user: Writer) -> SlotDetail:
    pe = _get(db, slot_id)
    document = db.get(Document, pe.document_id)
    assert document is not None
    ensure_editable(document)
    item = db.get(Equipment, body.equipment_id)
    if item is None or item.status == "rejected":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipamento não encontrado.")
    reference = db.get(Equipment, pe.default_equipment_id) if pe.default_equipment_id else None
    if reference is not None and item.category != reference.category:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Escolha um equipamento da mesma categoria.")  # fmt: skip
    reason = (body.reason or "").strip()
    if item.id != pe.default_equipment_id and len(reason) < 10:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Diga porque troca o equipamento (≥ 10 caracteres).")  # fmt: skip
    before = pe.equipment_id
    pe.equipment_id, pe.or_equivalent = item.id, item.or_equivalent or pe.or_equivalent
    pe.chosen_by, pe.chosen_at, pe.reason = user.id, datetime.now(UTC), reason or None
    record(db, user, "equipment.chosen", "project_equipment", pe.id,
           {"section_id": str(pe.section_id), "entry": pe.entry, "from": str(before),
            "to": str(item.id), "name": item.name, "manufacturer": item.manufacturer,
            "reference": item.id == pe.default_equipment_id},
           project_id=pe.project_id)  # fmt: skip
    db.commit()
    db.refresh(pe)
    return _detail(db, pe)
