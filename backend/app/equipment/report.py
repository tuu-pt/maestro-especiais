"""docs/fase7-fichas-R1.md: the reference equipment of an assembled CTE against the datasheets.

What screen F shows, written for the team: per slot, the datasheet, what was read from it (with
the page), the requirements of the CTE and the check. Written by the test of the datasheets of
R1 (`make fichas-report`); nothing here is a person's data.
"""

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.equipment.datasheets import current
from app.equipment.params import PARAMS, shown
from app.equipment.project import view
from app.models import Document, ProjectEquipment, Section

VERDICTS = {"ok": "Cumpre", "fails": "Não cumpre", "to_confirm": "Por confirmar",
            "no_datasheet": "Sem ficha", "no_requirements": "Sem requisitos",
            "no_equipment": "Sem equipamento"}  # fmt: skip
RESULTS = {"ok": "cumpre", "fails": "**não cumpre**", "unconfirmed_ok": "cumpre (por confirmar)",
           "unconfirmed_fails": "não cumpre (por confirmar)", "missing": "a ficha não diz",
           "not_comparable": "não comparável", "no_datasheet": "sem ficha"}  # fmt: skip
OPERATORS = {">=": "≥", "<=": "≤", "=": "=", ">=class": "≥", "info": ""}


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def report(db: Session, document: Document, intro: list[str], missing: list[str]) -> str:
    rows = db.scalars(select(ProjectEquipment).where(ProjectEquipment.document_id == document.id))
    order = {s.id: s.order for s in document.sections}
    slots = sorted(rows, key=lambda r: (order.get(r.section_id, 0), r.entry, r.slot))
    views = [view(db, pe) for pe in slots]
    count = Counter(v.verdict for v in views)
    with_sheet = sum(1 for v in views if v.item is not None and current(v.item) is not None)
    out = [*intro, "",
           f"{len(views)} equipamentos no CTE de R1 · {with_sheet} com ficha técnica · "
           + " · ".join(f"{VERDICTS[k]}: {n}" for k, n in count.most_common()), "",
           "## Equipamento a equipamento", "",
           "| Secção | Equipamento | Ficha | Lido da ficha (pág.) | Exigido no CTE → resultado "
           "| Verificação |",
           "|---|---|---|---|---|---|"]  # fmt: skip
    for v in views:
        section = db.get(Section, v.slot.section_id)
        item = v.item
        sheet = current(item) if item else None
        name = (f"{item.code + ' · ' if item and item.code else ''}{item.name if item else '—'}"
                + (f" ({item.manufacturer} {item.model or item.reference or ''}".rstrip() + ")"
                   if item else ""))  # fmt: skip
        read: list[str] = []
        if item and sheet:
            for p in item.params:
                if p.datasheet_id == sheet.id and PARAMS.get(p.name, None) is not None:
                    read.append(f"{shown(p.name, p.value)} ({p.page})")
        date = sheet.issue_date.isoformat() if sheet and sheet.issue_date else "sem data"
        checks = "; ".join(
            f"{c.label} {OPERATORS[c.operator]} {c.required} → {RESULTS[c.result]}"
            + (f" ({c.offered})" if c.offered else "")
            for c in v.checks
        )
        out.append(f"| {_cell(section.title if section else '')} | {_cell(name)} | "
                   f"{_cell(sheet.file_name + ' · ' + date) if sheet else '—'} | "
                   f"{_cell(', '.join(dict.fromkeys(read)) or '—')} | {_cell(checks or '—')} | "
                   f"{VERDICTS[v.verdict]} |")  # fmt: skip
    out += ["", "## Sem ficha técnica (fichas.json)", ""]
    out += [f"- {m}" for m in missing]
    return "\n".join(out) + "\n"


def summary(db: Session, document: Document) -> dict[str, Any]:
    rows = list(db.scalars(select(ProjectEquipment).where(
        ProjectEquipment.document_id == document.id)))  # fmt: skip
    views = [view(db, pe) for pe in rows]
    return {"slots": len(views),
            "with_datasheet": sum(1 for v in views if v.item and current(v.item) is not None),
            "verdicts": Counter(v.verdict for v in views)}  # fmt: skip
