"""EQP-02 (SPEC 9): the datasheet of an equipment is more than N years old (N = 3 by default,
EQUIPMENT_DATASHEET_MAX_AGE_YEARS). A datasheet without an issue date is information: the
curator writes it. One finding per item, whatever the number of slots it fills.
"""

from app.config import get_settings
from app.equipment.datasheets import is_old
from app.validation.context import Context
from app.validation.core import ASK_CURATOR, OPEN_EQUIPMENT, Finding, Rule
from app.validation.equipment import slots


def check(ctx: Context) -> list[Finding]:
    limit = get_settings().equipment_datasheet_max_age_years
    out, seen = [], set()
    for slot in slots(ctx):
        sheet = slot.sheet
        if sheet is None or slot.item.id in seen:
            continue
        seen.add(slot.item.id)
        if sheet.issue_date is None:
            out.append(RULE.finding(
                f"{slot.label}: a ficha técnica não tem data de emissão.",
                key=f"{slot.item.id}|no_date", severity="info", location=slot.where(),
                evidence={"equipment": slot.label, "datasheet": sheet.file_name},
                likely_reading="O curador escreve a data da ficha técnica.",
                actions=[OPEN_EQUIPMENT, ASK_CURATOR],
            ))  # fmt: skip
            continue
        if is_old(sheet, limit):
            out.append(RULE.finding(
                f"{slot.label}: a ficha técnica é de {sheet.issue_date:%m/%Y} (mais de {limit} "
                "anos).",
                key=f"{slot.item.id}|old|{sheet.id}", location=slot.where(),
                evidence={"equipment": slot.label, "datasheet": sheet.file_name,
                          "issue_date": sheet.issue_date.isoformat()},
                likely_reading="Ficha antiga: pedir ao fabricante a ficha atual.",
                suggested_fix="Carregar a ficha técnica atual na biblioteca (curador).",
                actions=[OPEN_EQUIPMENT, ASK_CURATOR],
            ))  # fmt: skip
    return out


RULE = Rule("EQP-02", "equipment", "warning", "Ficha técnica antiga", check)
