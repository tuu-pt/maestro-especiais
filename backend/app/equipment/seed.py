"""The equipment library and the requirements, proposed from the reference CTEs (Phase 7).

Runs after the blocks (app.library.seed): each CTE block about equipment is read in the
evidence of its source sections (SourceSection.units: placeholders, personal data masked), so
nothing of a person reaches the library. Idempotent: what is "proposed" is written again; what a
curator approved or rejected is left as it is (only new sources are added to it).
"""

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.equipment import block_category
from app.equipment.cte import Found, Need, category_of, read_section
from app.models import Equipment, EquipmentParam, Requirement, SourceSection, TemplateBlock


def _has_image(entry: dict[str, Any]) -> bool:
    ooxml = entry.get("ooxml") or ""
    return "<w:drawing" in ooxml or "imagedata" in ooxml


def _image_owner(found: list[Found], image_unit: int) -> Found | None:
    """The equipment an illustration belongs to: the reference line just before it."""
    before = [f for f in found if f.unit < image_unit]
    if before:
        return max(before, key=lambda f: f.unit)
    after = [f for f in found if f.unit > image_unit]
    return min(after, key=lambda f: f.unit) if after else None


class _Library:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rows = {e.identity: e for e in db.scalars(select(Equipment))}
        self.seen: set[str] = set()
        self.cte_params: dict[str, list[tuple[str, Any, str, str]]] = {}

    def put(self, found: Found, category: str, source: dict[str, Any]) -> Equipment:
        row = self.rows.get(found.identity)
        if row is None:
            row = Equipment(id=uuid.uuid4(), identity=found.identity, status="proposed",
                            sources=[])  # fmt: skip
            self.db.add(row)
            self.rows[found.identity] = row
        first = found.identity not in self.seen
        self.seen.add(found.identity)
        if row.status == "proposed" and first:
            row.category, row.name = category, found.name[:300]
            row.manufacturer, row.model = found.manufacturer, found.model
            row.reference, row.code = found.reference, found.code
            row.or_equivalent, row.sources, row.image = found.or_equivalent, [], None
            self.cte_params[found.identity] = []
        if not any(_same_source(s, source) for s in row.sources):
            row.sources = [*row.sources, source]
        if found.identity in self.cte_params:
            for r in found.readings:
                item = (r.name, r.value, r.unit, r.text)
                if all((p[0], p[1]) != (r.name, r.value) for p in self.cte_params[found.identity]):
                    self.cte_params[found.identity].append(item)
        return row

    def write_params(self) -> int:
        written = 0
        for identity, params in self.cte_params.items():
            row = self.rows[identity]
            row.params = [p for p in row.params if p.origin != "cte"] + [
                EquipmentParam(origin="cte", name=n, value=v, unit=u, text=t[:500],
                               review_status="extracted")
                for n, v, u, t in params
            ]  # fmt: skip
            written += len(params)
        return written

    def drop_stale(self) -> None:
        for identity, row in self.rows.items():
            if identity not in self.seen and row.status == "proposed" and not row.datasheets:
                self.db.delete(row)


def _same_source(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = ("project", "block_key", "unit")
    return all(a.get(k) == b.get(k) for k in keys)


def _requirements(db: Session, needs: list[tuple[TemplateBlock, str, Need, Equipment | None,
                                                dict[str, Any]]]) -> int:  # fmt: skip
    kept = list(db.scalars(select(Requirement).where(Requirement.doc_type == "CTE")))
    for r in kept:
        if r.status == "proposed":
            db.delete(r)
    decided = {(r.block_key, r.equipment_id, r.param_name, json.dumps(r.value)): r
               for r in kept if r.status != "proposed"}  # fmt: skip
    new: dict[tuple[Any, ...], Requirement] = {}
    for block, category, need, owner, source in needs:
        key = (block.key, owner.id if owner else None, need.param, json.dumps(need.value))
        if key in decided:
            continue
        row = new.get(key)
        if row is None:
            row = Requirement(doc_type="CTE", block_key=block.key, equipment_id=key[1],
                              category=category, param_name=need.param, operator=need.operator,
                              value=need.value, unit=need.unit, status="proposed",
                              sources=[])  # fmt: skip
            db.add(row)
            new[key] = row
        if not any(_same_source(s, source) for s in row.sources):
            row.sources = [*row.sources, source]
    return len(new)


def seed_equipment(db: Session) -> dict[str, int]:
    library = _Library(db)
    needs: list[tuple[TemplateBlock, str, Need, Equipment | None, dict[str, Any]]] = []
    blocks = db.scalars(select(TemplateBlock).where(
        TemplateBlock.doc_type == "CTE", TemplateBlock.version == 1, TemplateBlock.kind == "block",
    ).order_by(TemplateBlock.order))  # fmt: skip
    for block in blocks:
        category = block_category(block.key)
        if category is None:
            continue
        for ref in block.source_refs:
            section_id, project = ref.get("section_id"), ref["project"]
            section = db.get(SourceSection, uuid.UUID(section_id)) if section_id else None
            if section is None:
                continue
            lines = [(i, u.get("text") or "") for i, u in enumerate(section.units)
                     if u.get("kind") in ("paragraph", "table")]  # fmt: skip
            reading = read_section(block.key, lines, block.title)
            if reading is None:
                continue
            entry_of = {i: n for n, e in enumerate(block.body_template)
                        for i in (e.get("units") or {}).get(project, [])}  # fmt: skip
            rows: dict[int, Equipment] = {}
            for found in reading.found:
                source = {"project": project, "block_key": block.key, "section_id": section_id,
                          "entry": entry_of.get(found.unit), "unit": found.unit,
                          "text": found.text[:300]}  # fmt: skip
                rows[found.unit] = library.put(found, category_of(found, category), source)
            for n, entry in enumerate(block.body_template):
                units = (entry.get("units") or {}).get(project) or []
                if len(entry.get("units") or {}) != 1 or not units or not _has_image(entry):
                    continue
                owner = _image_owner(reading.found, units[0])
                row = rows.get(owner.unit) if owner else None
                if row is not None and row.status == "proposed" and row.image is None:
                    row.image = {"project": project, "block_key": block.key, "entry": n}
            for need in reading.needs:
                owner_row = rows.get(need.owner.unit) if need.owner else None
                source = {"project": project, "section_id": section_id, "unit": need.line,
                          "block_key": block.key, "text": need.text[:300]}  # fmt: skip
                needs.append((block, category, need, owner_row, source))
    db.flush()
    params = library.write_params()
    requirements = _requirements(db, needs)
    library.drop_stale()
    db.flush()
    return {"equipment": len(library.seen), "equipment_params": params,
            "requirements": requirements}  # fmt: skip
