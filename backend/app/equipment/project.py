"""The equipment of a project: one slot per reference line of its assembled CTE (Phase 7).

When the CTE is assembled, every block entry that names a reference equipment of the library
gets a ProjectEquipment with that item (the one of the reference project the entry comes from).
A person may choose another item of the same category (with a reason) or confirm this one:
only then the item's illustration goes into the .docx (an image of one reference project is
not assembled otherwise). The checks use the requirements of the project's block: of the whole
block and of the line the slot comes from; "ou equivalente" never asks for the brand.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.equipment.datasheets import current
from app.equipment.verify import Check, check, requirements_for, verdict
from app.models import BomItem, Document, Equipment, ProjectEquipment, Requirement, TemplateBlock

# the ficha-base key each category is linked to (SPEC 7.2), when there is one
FICHA_KEYS = {
    "portinhola": "eq.portinhola", "luminaria": "eq.luminarias", "quadro": "eq.quadros_modelo",
    "aparelhagem": "eq.aparelhagem_serie", "modulo_fv": "sys.fv", "inversor": "sys.fv",
    "carregador_ve": "sys.ve", "iluminacao_seguranca": "sys.iluminacao_seguranca",
}  # fmt: skip


def _image(entry: dict[str, Any]) -> bool:
    ooxml = entry.get("ooxml") or ""
    return "<w:drawing" in ooxml or "imagedata" in ooxml


def attach(db: Session, document: Document) -> int:
    """The slots of an assembled CTE, each with the library's item of its reference line."""
    if document.type != "CTE" or document.origin != "assembled":
        return 0
    by_entry: dict[tuple[str, int], list[tuple[str, Equipment]]] = defaultdict(list)
    for e in db.scalars(select(Equipment).where(Equipment.status != "rejected")):
        for s in e.sources:
            if s.get("entry") is not None:
                by_entry[(s["block_key"], s["entry"])].append((s["project"], e))
    written = 0
    for section in document.sections:
        if not section.active or section.block_id is None:
            continue
        block = db.get(TemplateBlock, section.block_id)
        if block is None:
            continue
        slots = []
        for n, entry in enumerate(block.body_template):
            found = [(p, e) for p, e in by_entry.get((block.key, n), [])
                     if p in (entry.get("units") or {})]  # fmt: skip
            if not found or (len(entry.get("units") or {}) == 1 and _image(entry)):
                continue
            own = [e for p, e in found if p == entry.get("project")] or [e for _, e in found]
            for slot, item in enumerate(dict.fromkeys(own)):
                db.add(ProjectEquipment(
                    project_id=document.project_id, document_id=document.id,
                    section_id=section.id, entry=n, slot=slot, block_key=block.key,
                    default_equipment_id=item.id, equipment_id=item.id,
                    or_equivalent=item.or_equivalent, ficha_key=FICHA_KEYS.get(item.category),
                ))  # fmt: skip
                slots.append({"entry": n, "slot": slot, "equipment_id": str(item.id),
                              "phase": 7})  # fmt: skip
                written += 1
        if slots:
            section.equipment_slots = slots
    db.flush()
    return written


def latest_cte(db: Session, project_id: Any) -> Document | None:
    return db.scalars(
        select(Document)
        .where(Document.project_id == project_id, Document.type == "CTE",
               Document.origin == "assembled")
        .order_by(Document.created_at.desc()).limit(1)
    ).first()  # fmt: skip


def slot_requirements(db: Session, pe: ProjectEquipment, *, approved_only: bool = False
                      ) -> list[Requirement]:  # fmt: skip
    """What the project's block asks of this slot: the whole block and the slot's own line."""
    found = requirements_for(db, {pe.block_key}, pe.default_equipment_id)
    return [r for r in found if r.status == "approved"] if approved_only else found


@dataclass
class Quantity:
    value: Decimal | None
    unit: str | None
    articles: list[str]  # "code · designation" of the MQT/LPU articles counted


def quantity(db: Session, revision_id: Any, pe: ProjectEquipment, item: Equipment) -> Quantity:
    """From the MQT/LPU of the ficha-base: luminaires by their code, the rest by the article
    linked to the slot's ficha key."""
    articles = list(db.scalars(select(BomItem).where(
        BomItem.revision_id == revision_id, BomItem.kind == "article")))  # fmt: skip
    if item.category == "luminaria" and item.code:
        codes = item.code.split("/")
        pattern = re.compile(rf"^\s*(?:{'|'.join(re.escape(c) for c in codes)})(?![\d.])", re.I)
        found = [a for a in articles if a.designation and pattern.match(a.designation)]
    elif pe.ficha_key and pe.ficha_key.startswith("eq."):
        found = [a for a in articles if a.link_key == pe.ficha_key]
    else:
        found = []
    units = {a.unit for a in found if a.unit}
    total = sum((a.quantity or Decimal(0) for a in found), Decimal(0)) if found else None
    return Quantity(total if len(units) <= 1 else None, units.pop() if len(units) == 1 else None,
                    [f"{a.code or ''} · {(a.designation or '')[:60]}" for a in found])  # fmt: skip


@dataclass
class SlotView:
    slot: ProjectEquipment
    item: Equipment | None
    checks: list[Check]
    verdict: str


def view(db: Session, pe: ProjectEquipment, item: Equipment | None = None) -> SlotView:
    item = item or pe.equipment
    if item is None:
        return SlotView(pe, None, [], "no_equipment")
    checks = check(item, slot_requirements(db, pe))
    return SlotView(pe, item, checks, verdict(checks, current(item) is not None))


def alternatives(db: Session, pe: ProjectEquipment) -> list[SlotView]:
    """Other items of the library of the same category, the ones that meet the slot first."""
    item = pe.equipment
    if item is None:
        return []
    others = db.scalars(select(Equipment).where(
        Equipment.category == item.category, Equipment.id != item.id,
        Equipment.status != "rejected").order_by(Equipment.name))  # fmt: skip
    rank = {"ok": 0, "to_confirm": 1, "no_requirements": 2, "no_datasheet": 3, "fails": 4}
    views = [view(db, pe, o) for o in others]
    return sorted(views, key=lambda v: rank.get(v.verdict, 5))


def chosen_images(db: Session, document: Document) -> dict[tuple[Any, int], list[str]]:
    """(section id, entry) -> OOXML of the illustrations of the items a person chose; with the
    relationships of their reference project (remapped by the .docx builder)."""
    out: dict[tuple[Any, int], list[str]] = defaultdict(list)
    rows = db.scalars(
        select(ProjectEquipment).where(
            ProjectEquipment.document_id == document.id, ProjectEquipment.chosen_by.is_not(None)
        )
    )
    for pe in rows:  # fmt: skip
        item = pe.equipment
        if item is None or not item.image:
            continue
        out[(pe.section_id, pe.entry)].append(_image_key(item.image))
    return out


def _image_key(image: dict[str, Any]) -> str:
    return f"{image['block_key']}#{image['entry']}#{image['project']}"


def image_fragment(db: Session, key: str) -> tuple[str, str, dict[str, Any]] | None:
    """(ooxml, project, rels) of an illustration kept by the library."""
    block_key, entry, project = key.split("#")
    block = db.scalars(select(TemplateBlock).where(
        TemplateBlock.key == block_key, TemplateBlock.version == 1)).first()  # fmt: skip
    if block is None or int(entry) >= len(block.body_template):
        return None
    ooxml = block.body_template[int(entry)].get("ooxml")
    if not ooxml:
        return None
    return ooxml, project, block.ooxml_rels.get(project, {})
