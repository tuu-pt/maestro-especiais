"""Datasheets of the library: stored in S3, read by patterns, one current per equipment (Phase 7).

A new datasheet becomes the current one and the previous turns "outdated" (its parameters stay,
for the history; the rules only read the current one). The same file twice is the same
datasheet (SHA-256).
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.datasheet import read_datasheet
from app.models import Datasheet, Equipment, EquipmentParam
from app.storage import ObjectStore


@dataclass
class Added:
    datasheet: Datasheet
    duplicate: bool


def _plus_years(since: date, years: int) -> date:
    try:
        return since.replace(year=since.year + years)
    except ValueError:  # 29 February
        return since.replace(year=since.year + years, day=28)


def is_old(sheet: Datasheet, years: int, today: date | None = None) -> bool:
    """Issued more than `years` ago (EQP-02); a datasheet without a date is not old, it is
    undated."""
    if sheet.issue_date is None:
        return False
    return _plus_years(sheet.issue_date, years) < (today or date.today())


def current(equipment: Equipment) -> Datasheet | None:
    return next((d for d in equipment.datasheets if d.status == "current"), None)


def add_datasheet(db: Session, store: ObjectStore, equipment: Equipment, filename: str,
                  data: bytes, user_id: str | None) -> Added:  # fmt: skip
    sha = hashlib.sha256(data).hexdigest()
    existing = db.scalars(select(Datasheet).where(
        Datasheet.equipment_id == equipment.id, Datasheet.sha256 == sha)).first()  # fmt: skip
    if existing is not None:
        return Added(existing, True)
    reading = read_datasheet(data)  # raises ReaderError on a broken PDF
    sheet = Datasheet(id=uuid.uuid4(), equipment_id=equipment.id, file_name=filename[:255],
                      sha256=sha, size=len(data), pages=reading.pages,
                      issue_date=reading.issue_date, issue_date_text=reading.issue_date_text,
                      language=reading.language, status="current", warnings=reading.warnings,
                      created_by=user_id)  # fmt: skip
    sheet.storage_key = f"equipment/{equipment.id}/datasheets/{sheet.id}"
    store.put(sheet.storage_key, data, "application/pdf")
    for old in equipment.datasheets:
        if old.status == "current":
            old.status = "outdated"
    db.add(sheet)
    for found in reading.params:
        r = found.reading
        db.add(EquipmentParam(equipment_id=equipment.id, datasheet_id=sheet.id, origin="datasheet",
                              name=r.name, value=r.value, unit=r.unit, text=r.text[:500],
                              page=found.page, review_status="extracted"))  # fmt: skip
    db.flush()
    db.refresh(equipment)
    return Added(sheet, False)
