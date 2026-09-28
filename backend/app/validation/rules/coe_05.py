"""COE-05 (SPEC 9): the power to supply differs between the ficha eletrotécnica, the
identification, the MDJ, the CTE and the first line of the Tabela de Cálculo (C6).

Read as numbers, never computed ("34,50" = 34,5). The reference is the ficha-base.
"""

from app.validation.compare import compare, evidence, location, observations, shown
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, OPEN_FICHA, Finding, Rule
from app.validation.extract.text import POWER
from app.validation.likely import reading

PIECES = ("FICHA_ELE", "IDENTIFICACAO", "TERMO", "MDJ", "CTE", "CALC")


def check(ctx: Context) -> list[Finding]:
    ref = ctx.ficha_value(POWER)
    obs = observations(ctx, POWER, PIECES)
    if ref is None or not obs:
        return []
    d = compare(ref, obs)
    if not d.divergent:
        return []
    values = "; ".join(f"{o.piece.name} {shown(o.fact.value)} kVA" for o in d.divergent)
    return [RULE.finding(
        f"Potência a alimentar diferente da ficha-base ({shown(ref)} kVA): {values}.",
        key=",".join(sorted(p.ref for p in d.pieces)),
        location=location(d.divergent[0].piece, d.divergent[0].fact),
        evidence={**evidence(ctx, ref, "ficha-base", obs, d.divergent), "unit": "kVA"},
        likely_reading=reading(d, ctx.ficha_date),
        suggested_fix="Corrigir a peça suspeita; a potência nunca é recalculada.",
        actions=[OPEN_EDITOR, OPEN_FICHA],
    )]  # fmt: skip


RULE = Rule("COE-05", "coherence", "critical", "Potência diferente entre peças", check)
