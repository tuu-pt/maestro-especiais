"""An equipment against the requirements of a CTE block: parameter by parameter (Phase 7).

Only the current datasheet counts (the CTE's own description of the reference model is not a
proof). For each requirement:
- ok / fails: a parameter a curator reviewed meets it, or none does;
- unconfirmed_ok / unconfirmed_fails: the same with parameters only extracted (EQP-01 asks to
  confirm them);
- missing: the datasheet does not say it; not_comparable: the values cannot be compared
  (IPX4 for IP54); no_datasheet: no current datasheet.
With "ou equivalente" the brand is never required: only the parameters (SPEC 10.F).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from app.equipment.datasheets import current
from app.equipment.params import PARAMS, satisfies, shown
from app.models import Equipment, EquipmentParam, Requirement

PASSING = ("ok", "unconfirmed_ok")


@dataclass
class Check:
    requirement_id: str
    param: str
    label: str
    operator: str
    required: str
    requirement_status: str
    block_key: str
    sources: list[Any]
    result: str
    offered: str | None = None
    page: int | None = None
    review_status: str | None = None
    param_id: str | None = None
    others: list[str] = field(default_factory=list)  # the other values of the datasheet


def block_keys(equipment: Equipment) -> set[str]:
    return {s["block_key"] for s in equipment.sources if s.get("block_key")}


def requirements_for(db: Session, keys: Iterable[str], equipment_id: Any = None
                     ) -> list[Requirement]:  # fmt: skip
    """The requirements of the blocks: of every equipment, and of this one."""
    keys = set(keys)
    if not keys:
        return []
    mine: ColumnElement[bool] = Requirement.equipment_id.is_(None)
    if equipment_id is not None:
        mine = or_(mine, Requirement.equipment_id == equipment_id)
    query = select(Requirement).where(Requirement.block_key.in_(keys), mine,
                                      Requirement.status != "rejected")  # fmt: skip
    return list(db.scalars(query.order_by(Requirement.block_key, Requirement.param_name)))


def _result(name: str, operator: str, required: Any, params: list[EquipmentParam]
            ) -> tuple[str, EquipmentParam | None]:  # fmt: skip
    if not params:
        return "missing", None
    for status in ("reviewed", "extracted"):
        own = [p for p in params if p.review_status == status]
        if not own:
            continue
        outcomes = [(satisfies(name, operator, required, p.value), p) for p in own]
        good = next((p for ok, p in outcomes if ok), None)
        prefix = "" if status == "reviewed" else "unconfirmed_"
        if good is not None:
            return prefix + "ok", good
        if any(ok is False for ok, _ in outcomes):
            return prefix + "fails", next(p for ok, p in outcomes if ok is False)
    return "not_comparable", params[0]


def check(equipment: Equipment, requirements: Iterable[Requirement]) -> list[Check]:
    sheet = current(equipment)
    params = [p for p in equipment.params if sheet is not None and p.datasheet_id == sheet.id]
    out = []
    for r in requirements:
        label = PARAMS[r.param_name].label if r.param_name in PARAMS else r.param_name
        item = Check(requirement_id=str(r.id), param=r.param_name, label=label,
                     operator=r.operator, required=shown(r.param_name, r.value),
                     requirement_status=r.status, block_key=r.block_key, sources=r.sources,
                     result="no_datasheet")  # fmt: skip
        if sheet is not None:
            own = [p for p in params if p.name == r.param_name]
            item.result, chosen = _result(r.param_name, r.operator, r.value, own)
            if chosen is not None:
                item.offered = shown(chosen.name, chosen.value)
                item.page, item.review_status = chosen.page, chosen.review_status
                item.param_id = str(chosen.id)
            item.others = [shown(p.name, p.value) for p in own if p is not chosen]
        out.append(item)
    return out


def verdict(checks: list[Check], has_datasheet: bool) -> str:
    """One word for a row of screen F."""
    results = {c.result for c in checks}
    if not has_datasheet:
        return "no_datasheet"
    if "fails" in results:
        return "fails"
    if not checks:
        return "no_requirements"
    if results & {"unconfirmed_fails", "unconfirmed_ok", "missing", "not_comparable"}:
        return "to_confirm"
    return "ok"
