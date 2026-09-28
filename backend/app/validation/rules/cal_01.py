"""CAL-01 (SPEC 9): compare values already in the Tabela de Cálculo. Nothing is computed.

IB ≤ In ≤ Iz and I2 ≤ 1,45·Iz, both read from the table (Phase 1; `check` also feeds the table
of circuits in the ficha, screen C). Phase 5: the total voltage drop and the breaking capacity of
each circuit, compared with the limits the MDJ states ("não deverá ser superior a 3% (…
iluminação) ou a 5% (… outros usos)"; "poder de corte nunca inferior a 6 kA"). The circuits of
the Tabela are feeders between boards: they are compared with the limit of other uses unless the
destination is lighting [A CONFIRMAR]. Without the limits in the MDJ the check is "não
comparável" (information), with the reason.
"""

import re
from decimal import Decimal
from itertools import pairwise
from typing import Literal

from app.ingest.detect import fold
from app.models import Circuit
from app.validation.context import Context
from app.validation.core import CONFIRM_SHEET, OPEN_FICHA, Finding, Rule
from app.validation.normalize import number, shown_number

Outcome = Literal["ok", "fail", "na"]

PENDING_NOTE = (
    "Queda de tensão e poder de corte: verificados na validação (ecrã E), com os limites que a "
    "MDJ indica."
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


_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_MIN_KA = re.compile(
    r"(?:nunca inferior|n[ãa]o inferior|m[íi]nim[oa])[^.]{0,40}?(\d+(?:[.,]\d+)?)\s*kA", re.I
)


def limits(ctx: Context) -> dict[str, tuple[float, str]]:
    """The limits the MDJ states: {"lighting"|"other"|"breaking": (value, where)}."""
    out: dict[str, tuple[float, str]] = {}
    for p in ctx.paragraphs("MDJ"):
        if "quedas_de_tensao" in p.section_key:
            for m in _PERCENT.finditer(p.text):
                after = fold(p.text[m.end() : m.end() + 45])
                value = number(m.group(1))
                kind = "lighting" if "ilumina" in after else "other" if "outros" in after else None
                if kind and value is not None:
                    out.setdefault(kind, (value, f"{p.section_title}, parágrafo {p.index + 1}"))
        minimum = _MIN_KA.search(p.text) if "poder_de_corte" in p.section_key else None
        if minimum:
            value = number(minimum.group(1))
            if value is not None:
                out.setdefault("breaking", (value, f"{p.section_title}, parágrafo {p.index + 1}"))
    return out


def where(circuit: Circuit) -> str:
    return f"{circuit.origin or '?'} → {circuit.destination or '?'}"


def calc_piece(ctx: Context) -> str | None:
    return next((p.ref for p in ctx.of_kind("CALC")), None)


def _limit_findings(ctx: Context) -> list[Finding]:
    found = limits(ctx)
    out = []
    missing = [n for n, k in (("queda de tensão", "other"), ("poder de corte", "breaking"))
               if k not in found]  # fmt: skip
    if missing and ctx.circuits:
        why = ("não há MDJ" if not ctx.of_kind("MDJ")
               else "a MDJ não indica o limite")  # fmt: skip
        out.append(RULE.finding(
            f"{' e '.join(missing).capitalize()}: não comparável ({why}).",
            key="not_comparable|" + ",".join(missing), severity="info",
            location={"piece": calc_piece(ctx)},
            evidence={"not_comparable": missing, "reason": why},
            likely_reading="Não comparável: sem o limite do projeto na MDJ.",
        ))  # fmt: skip
    for c in ctx.circuits:
        lighting = "ilumina" in fold(c.destination or "")
        vd_key = "lighting" if lighting and "lighting" in found else "other"
        checks = []
        if vd_key in found and c.vd_total_pct is not None:
            limit, source = found[vd_key]
            vd = shown_number(float(c.vd_total_pct))
            if float(c.vd_total_pct) > limit:
                text = f"queda de tensão total {vd} % acima do limite de {shown_number(limit)} %"
                checks.append(("vd", text + " da MDJ", source))
        if "breaking" in found and c.breaking_capacity_ka is not None:
            limit, source = found["breaking"]
            pdc = shown_number(float(c.breaking_capacity_ka))
            if float(c.breaking_capacity_ka) < limit:
                text = f"poder de corte {pdc} kA abaixo do mínimo de {shown_number(limit)} kA"
                checks.append(("pdc", text + " da MDJ", source))
        for name, text, source in checks:
            out.append(RULE.finding(
                f"Troço {where(c)}: {text}.",
                key=f"{where(c)}|{c.row_index}|{name}",
                location={"piece": calc_piece(ctx), "cell": c.source_ref, "circuit_id": str(c.id)},
                evidence={"circuit": where(c), "check": text, "limit_from": f"MDJ · {source}",
                          "source": c.source_ref},
                likely_reading="Confirmar na folha de cálculo.",
                suggested_fix="O projetista confirma os valores na folha; nada é recalculado.",
                actions=[CONFIRM_SHEET, OPEN_FICHA],
            ))  # fmt: skip
    return out


def run(ctx: Context) -> list[Finding]:
    out = _limit_findings(ctx)
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
