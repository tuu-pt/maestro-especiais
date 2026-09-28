"""CAL-01 (SPEC 9): compare values already in the Tabela de Cálculo. Nothing is computed.

IB ≤ In ≤ Iz and I2 ≤ 1,45·Iz, both read from the table (Phase 1; `check` also feeds the table
of circuits in the ficha, screen C). The voltage-drop and breaking-capacity checks compare with
the limits stated in the MDJ (Phase 5, task 4c).
"""

from decimal import Decimal
from itertools import pairwise
from typing import Literal

from app.models import Circuit
from app.validation.context import Context
from app.validation.core import CONFIRM_SHEET, OPEN_FICHA, Finding, Rule
from app.validation.normalize import shown_number

Outcome = Literal["ok", "fail", "na"]

PENDING_NOTE = (
    "Queda de tensão e poder de corte: a verificação fica disponível quando houver MDJ com os "
    "limites do projeto."
)
CHECKS = {
    "ib_in_iz": ("IB ≤ In ≤ Iz", (("IB", "ib_a"), ("In", "in_a"), ("Iz", "iz_a"))),
    "i2_iz145": ("I2 ≤ 1,45·Iz", (("I2", "i2_a"), ("1,45·Iz", "iz145_a"))),
}


def _le(*values: Decimal | None) -> Outcome:
    if any(v is None for v in values):
        return "na"
    pairs = pairwise(values)
    return "ok" if all(a <= b for a, b in pairs if a is not None and b is not None) else "fail"


def check(circuit: Circuit) -> dict[str, Outcome]:
    return {
        "ib_in_iz": _le(circuit.ib_a, circuit.in_a, circuit.iz_a),
        "i2_iz145": _le(circuit.i2_a, circuit.iz145_a),
    }


def where(circuit: Circuit) -> str:
    return f"{circuit.origin or '?'} → {circuit.destination or '?'}"


def calc_piece(ctx: Context) -> str | None:
    return next((p.ref for p in ctx.of_kind("CALC")), None)


def run(ctx: Context) -> list[Finding]:
    out = []
    for c in ctx.circuits:
        for name, outcome in check(c).items():
            if outcome != "fail":
                continue
            label, fields = CHECKS[name]
            values = {n: shown_number(float(getattr(c, f))) + " A" for n, f in fields}
            shown = "; ".join(f"{n} = {v}" for n, v in values.items())
            out.append(RULE.finding(
                f"Troço {where(c)}: {label} não se verifica com os valores da Tabela de Cálculo "
                f"({shown}).",
                key=f"{where(c)}|{c.row_index}|{name}",
                location={"piece": calc_piece(ctx), "cell": c.source_ref,
                          "circuit_id": str(c.id)},
                evidence={"circuit": where(c), "check": label, "values": values,
                          "source": c.source_ref},
                likely_reading="Confirmar na folha de cálculo.",
                suggested_fix="O projetista confirma os valores na folha; nada é recalculado.",
                actions=[CONFIRM_SHEET, OPEN_FICHA],
            ))  # fmt: skip
    return out


RULE = Rule("CAL-01", "calculation", "warning", "Verificação da Tabela de Cálculo", run)
