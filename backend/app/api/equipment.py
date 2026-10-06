"""Equipment library for the curator (SPEC 7.6, screen G): items, datasheets, parameters,
requirements.

Everyone reads it; only a curator adds datasheets, reviews parameters and requirements, and
approves or rejects an item. Every decision is audited (no project: the library belongs to no
project). Datasheets are public documents of the manufacturers.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.equipment import CATEGORIES
from app.equipment.datasheets import add_datasheet, current, is_old
from app.equipment.params import PARAMS, normalize, shown
from app.equipment.verify import block_keys, check, requirements_for, verdict
from app.ingest.pipeline import ReaderError
from app.models import Datasheet, Equipment, EquipmentParam, Requirement
from app.storage import ObjectStore, get_store

router = APIRouter(prefix="/equipment", tags=["biblioteca de equipamentos"])

DB = Annotated[Session, Depends(get_session)]
Curador = Annotated[User, Depends(require_role("curador"))]
Store = Annotated[ObjectStore, Depends(get_store)]


class DatasheetOut(BaseModel):
    id: uuid.UUID
    file_name: str
    size: int
    pages: int
    issue_date: date | None
    issue_date_text: str | None
    language: str | None
    status: str
    warnings: list[str]
    created_at: datetime
    old: bool  # older than EQUIPMENT_DATASHEET_MAX_AGE_YEARS (EQP-02)


class ParamOut(BaseModel):
    id: uuid.UUID
    name: str
    label: str
    value: Any
    shown: str
    unit: str
    origin: str
    text: str
    page: int | None
    datasheet_id: uuid.UUID | None
    review_status: str
    reviewed_by: str | None


class EquipmentSummary(BaseModel):
    id: uuid.UUID
    category: str
    category_label: str
    name: str
    manufacturer: str
    model: str | None
    reference: str | None
    code: str | None
    or_equivalent: bool
    status: str
    projects: list[str]
    datasheet: DatasheetOut | None
    params_reviewed: int
    params_to_review: int
    verdict: str


class CheckOut(BaseModel):
    requirement_id: str
    param: str
    label: str
    operator: str
    required: str
    requirement_status: str
    block_key: str
    result: str
    offered: str | None
    page: int | None
    review_status: str | None
    param_id: str | None
    others: list[str]
    evidence: list[str]


class EquipmentDetail(EquipmentSummary):
    sources: list[dict[str, Any]]
    image: dict[str, Any] | None
    params: list[ParamOut]
    datasheets: list[DatasheetOut]
    checks: list[CheckOut]
    review_note: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class EquipmentEditIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    manufacturer: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=200)
    category: str | None = None
    or_equivalent: bool | None = None
    note: str = Field(min_length=3, max_length=2000)  # why: it goes to the audit


class ParamEditIn(BaseModel):
    value: Any = None  # a correction; None keeps the value
    page: int | None = Field(default=None, ge=1)
    reviewed: bool = True


class ParamAddIn(BaseModel):
    name: str
    value: Any
    page: int | None = Field(default=None, ge=1)


class DatasheetEditIn(BaseModel):
    issue_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}(-\d{2})?$")
    language: Literal["pt", "en", "es", "fr", "de", "it"] | None = None


class RequirementOut(BaseModel):
    id: uuid.UUID
    block_key: str
    equipment_id: uuid.UUID | None
    category: str
    param_name: str
    label: str
    operator: str
    value: Any
    shown: str
    status: str
    sources: list[dict[str, Any]]


class RequirementEditIn(BaseModel):
    decision: Literal["approved", "rejected"] | None = None
    operator: Literal[">=", "<=", "=", ">=class", "info"] | None = None
    value: Any = None
    note: str | None = Field(default=None, max_length=2000)


class CategoryOut(BaseModel):
    id: str
    label: str


class ParamInfo(BaseModel):
    name: str
    label: str
    unit: str
    operator: str


# ---------------------------------------------------------------- helpers


def _equipment(db: Session, equipment_id: uuid.UUID) -> Equipment:
    item = db.get(Equipment, equipment_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipamento não encontrado.")
    return item


def _sheet(d: Datasheet) -> DatasheetOut:
    old = is_old(d, get_settings().equipment_datasheet_max_age_years)
    return DatasheetOut(id=d.id, file_name=d.file_name, size=d.size, pages=d.pages,
                        issue_date=d.issue_date, issue_date_text=d.issue_date_text,
                        language=d.language, status=d.status, warnings=d.warnings,
                        created_at=d.created_at, old=old)  # fmt: skip


def _param(p: EquipmentParam) -> ParamOut:
    info = PARAMS.get(p.name)
    return ParamOut(id=p.id, name=p.name, label=info.label if info else p.name, value=p.value,
                    shown=shown(p.name, p.value), unit=p.unit, origin=p.origin, text=p.text,
                    page=p.page, datasheet_id=p.datasheet_id, review_status=p.review_status,
                    reviewed_by=p.reviewed_by)  # fmt: skip


def _summary(db: Session, e: Equipment) -> dict[str, Any]:
    sheet = current(e)
    own = [p for p in e.params if sheet is not None and p.datasheet_id == sheet.id]
    checks = check(e, requirements_for(db, block_keys(e), e.id))
    return {
        "id": e.id, "category": e.category,
        "category_label": CATEGORIES.get(e.category, e.category),
        "name": e.name, "manufacturer": e.manufacturer, "model": e.model,
        "reference": e.reference, "code": e.code, "or_equivalent": e.or_equivalent,
        "status": e.status, "projects": sorted({s["project"] for s in e.sources}),
        "datasheet": _sheet(sheet) if sheet else None,
        "params_reviewed": sum(p.review_status == "reviewed" for p in own),
        "params_to_review": sum(p.review_status == "extracted" for p in own),
        "verdict": verdict(checks, sheet is not None),
    }  # fmt: skip


def _check_out(c: Any) -> CheckOut:
    evidence = [f"{s.get('project')}: «{s.get('text')}»" for s in c.sources]
    return CheckOut(**{k: v for k, v in vars(c).items() if k != "sources"}, evidence=evidence)


def detail(db: Session, e: Equipment) -> EquipmentDetail:
    checks = check(e, requirements_for(db, block_keys(e), e.id))
    return EquipmentDetail(
        **_summary(db, e), sources=e.sources, image=e.image,
        params=[_param(p) for p in sorted(e.params, key=lambda p: (p.origin, p.name))],
        datasheets=[_sheet(d) for d in sorted(e.datasheets, key=lambda d: d.status != "current")],
        checks=[_check_out(c) for c in checks],
        review_note=e.review_note, reviewed_by=e.reviewed_by, reviewed_at=e.reviewed_at,
    )  # fmt: skip


def _requirement(r: Requirement) -> RequirementOut:
    info = PARAMS.get(r.param_name)
    return RequirementOut(id=r.id, block_key=r.block_key, equipment_id=r.equipment_id,
                          category=r.category, param_name=r.param_name,
                          label=info.label if info else r.param_name, operator=r.operator,
                          value=r.value, shown=shown(r.param_name, r.value), status=r.status,
                          sources=r.sources)  # fmt: skip


def _audit(db: Session, user: User, action: str, e: Equipment, payload: dict[str, Any]) -> None:
    payload = {"name": e.name, "manufacturer": e.manufacturer, **payload}
    record(db, user, action, "equipment", e.id, payload, project_id=None)


# ---------------------------------------------------------------- read


@router.get("/categories")
def categories(_: CurrentUser) -> list[CategoryOut]:
    return [CategoryOut(id=k, label=v) for k, v in CATEGORIES.items()]


@router.get("/params")
def params(_: CurrentUser) -> list[ParamInfo]:
    return [ParamInfo(name=p.name, label=p.label, unit=p.unit, operator=p.operator)
            for p in PARAMS.values()]  # fmt: skip


@router.get("")
def list_equipment(
    db: DB, _: CurrentUser,
    category: Annotated[str | None, Query()] = None,
    status_: Annotated[Literal["proposed", "approved", "rejected"] | None,
                       Query(alias="status")] = None,
) -> list[EquipmentSummary]:  # fmt: skip
    query = select(Equipment).order_by(Equipment.category, Equipment.code, Equipment.name)
    if category:
        query = query.where(Equipment.category == category)
    if status_:
        query = query.where(Equipment.status == status_)
    return [EquipmentSummary(**_summary(db, e)) for e in db.scalars(query)]


@router.get("/requirements")
def list_requirements(
    db: DB, _: CurrentUser, block_key: Annotated[str | None, Query()] = None
) -> list[RequirementOut]:
    query = select(Requirement).order_by(Requirement.block_key, Requirement.param_name)
    if block_key:
        query = query.where(Requirement.block_key == block_key)
    return [_requirement(r) for r in db.scalars(query)]


@router.get("/{equipment_id}")
def get_equipment(equipment_id: uuid.UUID, db: DB, _: CurrentUser) -> EquipmentDetail:
    return detail(db, _equipment(db, equipment_id))


@router.get("/datasheets/{datasheet_id}/file")
def datasheet_file(datasheet_id: uuid.UUID, db: DB, store: Store, _: CurrentUser) -> Response:
    sheet = db.get(Datasheet, datasheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ficha técnica não encontrada.")
    safe = sheet.file_name.encode("ascii", "replace").decode().replace('"', "")
    return Response(store.get(sheet.storage_key), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{safe}"'})  # fmt: skip


# ---------------------------------------------------------------- curator


@router.post("/{equipment_id}/datasheets", status_code=status.HTTP_201_CREATED)
def upload_datasheet(
    equipment_id: uuid.UUID, db: DB, user: Curador, store: Store,
    settings: Annotated[Settings, Depends(get_settings)], response: Response,
    upload: Annotated[UploadFile, File(alias="file")],
) -> EquipmentDetail:  # fmt: skip
    e = _equipment(db, equipment_id)
    data = upload.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Ficheiro demasiado grande.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "A ficha técnica tem de ser um PDF.")  # fmt: skip
    name = (upload.filename or "ficha.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    try:
        added = add_datasheet(db, store, e, name, data, user.id)
    except ReaderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if added.duplicate:
        response.status_code = status.HTTP_200_OK
    else:
        sheet = added.datasheet
        _audit(db, user, "equipment.datasheet_added", e,
               {"file": sheet.file_name, "sha256": sheet.sha256, "pages": sheet.pages,
                "params": sum(1 for p in e.params if p.datasheet_id == sheet.id)})  # fmt: skip
    db.commit()
    return detail(db, e)


@router.patch("/datasheets/{datasheet_id}")
def edit_datasheet(datasheet_id: uuid.UUID, body: DatasheetEditIn, db: DB, user: Curador
                   ) -> EquipmentDetail:  # fmt: skip
    sheet = db.get(Datasheet, datasheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ficha técnica não encontrada.")
    changed: dict[str, Any] = {}
    if body.issue_date is not None:
        parts = [int(x) for x in body.issue_date.split("-")]
        try:
            when = date(parts[0], parts[1], parts[2] if len(parts) > 2 else 1)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Data inválida.") from exc
        changed["issue_date"] = {"from": str(sheet.issue_date), "to": str(when)}
        sheet.issue_date, sheet.issue_date_text = when, "escrita pelo curador"
    if body.language is not None:
        changed["language"] = {"from": sheet.language, "to": body.language}
        sheet.language = body.language
    if not changed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Não há alterações.")
    _audit(db, user, "equipment.datasheet_edited", sheet.equipment,
           {"file": sheet.file_name, "changed": changed})  # fmt: skip
    db.commit()
    return detail(db, sheet.equipment)


@router.patch("/params/{param_id}")
def edit_param(param_id: uuid.UUID, body: ParamEditIn, db: DB, user: Curador) -> EquipmentDetail:
    p = db.get(EquipmentParam, param_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parâmetro não encontrado.")
    if p.origin != "datasheet":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Só se revêem os parâmetros das fichas técnicas.")  # fmt: skip
    changed: dict[str, Any] = {}
    if body.value is not None:
        try:
            value = normalize(p.name, body.value)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        if value != p.value:
            changed["value"] = {"from": p.value, "to": value}
            p.value = value
    if body.page is not None and body.page != p.page:
        changed["page"] = {"from": p.page, "to": body.page}
        p.page = body.page
    p.review_status = "reviewed" if body.reviewed else "extracted"
    p.reviewed_by, p.reviewed_at = (user.id, datetime.now(UTC)) if body.reviewed else (None, None)
    _audit(db, user, "equipment.param_reviewed" if body.reviewed else "equipment.param_reopened",
           p.equipment, {"param": p.name, "value": p.value, "changed": changed})  # fmt: skip
    db.commit()
    return detail(db, p.equipment)


@router.post("/{equipment_id}/params", status_code=status.HTTP_201_CREATED)
def add_param(equipment_id: uuid.UUID, body: ParamAddIn, db: DB, user: Curador
              ) -> EquipmentDetail:  # fmt: skip
    """A parameter the patterns did not read, written by the curator from the datasheet."""
    e = _equipment(db, equipment_id)
    sheet = current(e)
    if sheet is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Carregue primeiro a ficha técnica.")
    try:
        value = normalize(body.name, body.value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    db.add(EquipmentParam(equipment_id=e.id, datasheet_id=sheet.id, origin="datasheet",
                          name=body.name, value=value, unit=PARAMS[body.name].unit,
                          text="escrito pelo curador", page=body.page, review_status="reviewed",
                          reviewed_by=user.id, reviewed_at=datetime.now(UTC)))  # fmt: skip
    _audit(db, user, "equipment.param_added", e, {"param": body.name, "value": value})
    db.commit()
    db.refresh(e)
    return detail(db, e)


@router.post("/{equipment_id}/review")
def review_equipment(equipment_id: uuid.UUID, body: DecisionIn, db: DB, user: Curador
                     ) -> EquipmentDetail:  # fmt: skip
    e = _equipment(db, equipment_id)
    before = e.status
    e.status, e.reviewed_by, e.reviewed_at = body.decision, user.id, datetime.now(UTC)
    e.review_note = (body.note or "").strip() or None
    _audit(db, user, f"equipment.{body.decision}", e, {"from": before})
    db.commit()
    return detail(db, e)


@router.patch("/{equipment_id}")
def edit_equipment(equipment_id: uuid.UUID, body: EquipmentEditIn, db: DB, user: Curador
                   ) -> EquipmentDetail:  # fmt: skip
    """An approved item that is edited goes back to "proposed" (as the blocks)."""
    e = _equipment(db, equipment_id)
    if body.category is not None and body.category not in CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Categoria desconhecida.")
    changed: dict[str, Any] = {}
    for field_ in ("name", "manufacturer", "model", "reference", "category", "or_equivalent"):
        value = getattr(body, field_)
        if isinstance(value, str):
            value = value.strip() or None
        if value is not None and value != getattr(e, field_):
            changed[field_] = {"from": getattr(e, field_), "to": value}
            setattr(e, field_, value)
    if not changed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Não há alterações.")
    was = e.status
    if e.status != "proposed":
        e.status, e.reviewed_by, e.reviewed_at, e.review_note = "proposed", None, None, None
    _audit(db, user, "equipment.edited", e,
           {"changed": changed, "note": body.note.strip(), "from": was})  # fmt: skip
    db.commit()
    return detail(db, e)


@router.patch("/requirements/{requirement_id}")
def edit_requirement(requirement_id: uuid.UUID, body: RequirementEditIn, db: DB, user: Curador
                     ) -> RequirementOut:  # fmt: skip
    r = db.get(Requirement, requirement_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requisito não encontrado.")
    changed: dict[str, Any] = {}
    if body.value is not None:
        try:
            value = normalize(r.param_name, body.value)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        if value != r.value:
            changed["value"] = {"from": r.value, "to": value}
            r.value = value
    if body.operator is not None and body.operator != r.operator:
        changed["operator"] = {"from": r.operator, "to": body.operator}
        r.operator = body.operator
    if body.decision is not None:
        changed["status"] = {"from": r.status, "to": body.decision}
        r.status, r.reviewed_by, r.reviewed_at = body.decision, user.id, datetime.now(UTC)
    elif changed and r.status != "proposed":
        changed["status"] = {"from": r.status, "to": "proposed"}
        r.status, r.reviewed_by, r.reviewed_at = "proposed", None, None
    if not changed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Não há alterações.")
    r.review_note = (body.note or "").strip() or r.review_note
    record(db, user, "equipment.requirement_reviewed", "equipment_requirement", r.id,
           {"block_key": r.block_key, "param": r.param_name, "changed": changed},
           project_id=None)  # fmt: skip
    db.commit()
    return _requirement(r)
