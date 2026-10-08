"""What the EQP rules share: the equipment slots of the assembled CTE of the run (Phase 7)."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.equipment.datasheets import current
from app.models import Datasheet, Equipment, ProjectEquipment, Section
from app.validation.compare import location
from app.validation.context import Context
from app.validation.pieces import Piece

OPERATORS = {">=": "≥", "<=": "≤", "=": "=", ">=class": "≥", "info": ""}


@dataclass
class Slot:
    piece: Piece
    pe: ProjectEquipment
    item: Equipment
    sheet: Datasheet | None
    section_title: str

    @property
    def label(self) -> str:
        model = " ".join(x for x in (self.item.manufacturer, self.item.model or self.item.reference)
                         if x)  # fmt: skip
        code = f"{self.item.code} · " if self.item.code else ""
        return f"{code}{self.item.name} ({model})"

    def where(self) -> dict[str, Any]:
        return {**location(self.piece), "section_id": str(self.pe.section_id),
                "section_title": self.section_title, "equipment_slot": str(self.pe.id)}  # fmt: skip


def slots(ctx: Context) -> list[Slot]:
    if "equipment_slots" in ctx.memo:
        return list(ctx.memo["equipment_slots"])
    found: list[Slot] = []
    if ctx.db is not None:
        for piece in ctx.of_kind("CTE"):
            if piece.origin != "assembled" or not piece.document_id:
                continue
            rows = ctx.db.scalars(select(ProjectEquipment).where(
                ProjectEquipment.document_id == uuid.UUID(piece.document_id)))  # fmt: skip
            for pe in rows:
                item = pe.equipment
                if item is None:
                    continue
                section = ctx.db.get(Section, pe.section_id)
                found.append(Slot(piece, pe, item, current(item), section.title if section else ""))
    ctx.memo["equipment_slots"] = found
    return list(found)
