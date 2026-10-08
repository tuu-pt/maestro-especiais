"""EQP-03 (SPEC 9): a reference equipment of the CTE has no datasheet in the library.

Information, one finding per item (an item may fill several slots): the curator adds the
manufacturer's datasheet; until then EQP-01 cannot compare it.
"""

from app.validation.context import Context
from app.validation.core import ASK_CURATOR, OPEN_EQUIPMENT, Finding, Rule
from app.validation.equipment import slots


def check(ctx: Context) -> list[Finding]:
    out, seen = [], set()
    for slot in slots(ctx):
        if slot.sheet is not None or slot.item.id in seen:
            continue
        seen.add(slot.item.id)
        sections = sorted({s.section_title for s in slots(ctx) if s.item.id == slot.item.id})
        out.append(RULE.finding(
            f"{slot.label}: sem ficha técnica na biblioteca ({', '.join(sections)}).",
            key=f"{slot.item.id}|no_datasheet", location=slot.where(),
            evidence={"equipment": slot.label},
            likely_reading="Pedir ao curador a ficha técnica do fabricante.",
            actions=[OPEN_EQUIPMENT, ASK_CURATOR],
        ))  # fmt: skip
    return out


RULE = Rule("EQP-03", "equipment", "info", "Equipamento sem ficha técnica", check)
