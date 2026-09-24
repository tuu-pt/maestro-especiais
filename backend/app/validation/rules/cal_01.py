"""CAL-01 (SPEC 9): compare values already in the Tabela de Cálculo. Nothing is computed.

Phase 1 covers IB ≤ In ≤ Iz and I2 ≤ 1,45·Iz, both read from the table. The voltage-drop and
breaking-capacity checks need the limits stated in the MDJ and wait for it.
"""

from decimal import Decimal
from itertools import pairwise
from typing import Literal

from app.models import Circuit

Outcome = Literal["ok", "fail", "na"]

PENDING_NOTE = (
    "Queda de tensão e poder de corte: a verificação fica disponível quando houver MDJ com os "
    "limites do projeto."
)


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
