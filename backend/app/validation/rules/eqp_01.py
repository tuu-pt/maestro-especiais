"""EQP-01 (SPEC 9): a parameter of the datasheet does not meet the requirement of the CTE.

Each equipment slot of the assembled CTE against the approved requirements of its block (of the
whole block and of the slot's line), with the current datasheet of the chosen item:
- a reviewed parameter that fails: critical;
- parameters only extracted (not reviewed by the curator): a warning, "confirmar parâmetro";
- the datasheet does not say it, or the values cannot be compared: information.
"Ou equivalente": only the minimums are compared, never the brand. Without a datasheet, EQP-03.
"""

from app.equipment.project import slot_requirements
from app.equipment.verify import check
from app.validation.context import Context
from app.validation.core import ASK_CURATOR, OPEN_EQUIPMENT, Finding, Rule
from app.validation.equipment import OPERATORS, slots


def _quote(sources: list[dict[str, str]]) -> str | None:
    return next((s.get("text") for s in sources if s.get("text")), None)


def check_rule(ctx: Context) -> list[Finding]:
    out = []
    for slot in slots(ctx):
        if slot.sheet is None:
            continue
        checks = check(slot.item, slot_requirements(ctx.db, slot.pe, approved_only=True))
        to_confirm = [c for c in checks if c.result.startswith("unconfirmed_")]
        not_said = [c for c in checks if c.result in ("missing", "not_comparable")]
        for c in (c for c in checks if c.result == "fails"):
            out.append(RULE.finding(
                f"{slot.label} não cumpre o CTE · {slot.section_title}: {c.label} exigido "
                f"{OPERATORS[c.operator]} {c.required}; a ficha técnica indica {c.offered}"
                + (f" (pág. {c.page})." if c.page else "."),
                key=f"{slot.pe.id}|{c.param}|fails", location=slot.where(),
                evidence={"equipment": slot.label, "check": c.label,
                          "required": f"{OPERATORS[c.operator]} {c.required}",
                          "offered": c.offered, "page": c.page,
                          "datasheet": slot.sheet.file_name, "excerpt": _quote(c.sources)},
                likely_reading="O equipamento escolhido não cumpre: escolher uma alternativa da "
                "biblioteca ou rever o requisito no CTE.",
                suggested_fix="Trocar pela alternativa que cumpre, ou corrigir o requisito do "
                "bloco (curador).",
                actions=[OPEN_EQUIPMENT, ASK_CURATOR],
            ))  # fmt: skip
        if to_confirm:
            names = ", ".join(f"{c.label} ({c.offered})" for c in to_confirm)
            out.append(RULE.finding(
                f"{slot.label} · {slot.section_title}: confirmar na ficha técnica {names} "
                "(lidos automaticamente, ainda não revistos pelo curador).",
                key=f"{slot.pe.id}|confirm", severity="warning", location=slot.where(),
                evidence={"equipment": slot.label, "datasheet": slot.sheet.file_name,
                          "check": [c.label for c in to_confirm]},
                likely_reading="Confirmar parâmetro: o curador revê os valores lidos da ficha.",
                actions=[OPEN_EQUIPMENT, ASK_CURATOR],
            ))  # fmt: skip
        if not_said:
            names = ", ".join(c.label for c in not_said)
            out.append(RULE.finding(
                f"{slot.label} · {slot.section_title}: a ficha técnica não diz {names}.",
                key=f"{slot.pe.id}|not_said", severity="info", location=slot.where(),
                evidence={"equipment": slot.label, "datasheet": slot.sheet.file_name,
                          "not_comparable": [c.label for c in not_said]},
                likely_reading="Não comparável: pedir ao curador que escreva o valor da ficha.",
                actions=[OPEN_EQUIPMENT, ASK_CURATOR],
            ))  # fmt: skip
    return out


RULE = Rule("EQP-01", "equipment", "critical", "Equipamento não cumpre o CTE", check_rule)
