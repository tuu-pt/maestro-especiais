"""The coherence matrix of the project (SPEC 10.E), built from the same facts as the rules.

The ficha-base is the reference; the columns are the pieces (MDJ, CTE, MQT/LPU, Ficha ELE,
Identificação/Termo, Tabela de Cálculo, Desenhos); the rows are the minimum of the SPEC. Each
cell says what the piece says (masked when personal) and whether it differs from the reference;
the "Leitura" of a row is the likely reading of the issue about it, or "Coerente". Personal
values are compared in the backend and never leave it.
"""

from collections.abc import Callable
from typing import Any

from app.validation.compare import observations, shown
from app.validation.context import Context
from app.validation.core import Finding
from app.validation.extract.text import (
    CABLE,
    LUMINAIRE_TYPES,
    POWER,
    PV_KWP,
    QTY_BOARDS,
    QTY_EV,
)
from app.validation.likely import Observation, reading, split
from app.validation.normalize import same
from app.validation.pieces import COLUMNS, MASK
from app.validation.rules import coe_01
from app.validation.rules.coe_04 import equal

COHERENT = "Coerente"
NO_DATA = "Sem dados para comparar"


def _row(ctx: Context, label: str, reference: Any, obs: list[Observation],
         eq: Callable[[Any, Any], bool], finding: Finding | None,
         personal: bool = False, unit: str = "") -> dict[str, Any]:  # fmt: skip
    d = split(reference, obs, eq) if reference is not None else None
    bad = {o.piece.ref for o in d.divergent} if d else set()
    if finding is not None:
        bad |= {v["piece"] for v in finding.evidence.get("values", []) if v.get("differs")}
        bad |= {p["piece"] for p in finding.evidence.get("pieces", [])}
    cells: dict[str, dict[str, Any]] = {}
    for o in obs:
        cell = cells.setdefault(o.piece.column, {"values": [], "differs": False, "pieces": []})
        value = MASK if personal or o.fact.personal else shown(o.fact.value)
        if value not in cell["values"]:
            cell["values"].append(value)
        cell["pieces"].append(o.piece.name)
        cell["differs"] = cell["differs"] or o.piece.ref in bad
    text = finding.likely_reading if finding else None
    if text is None and d is not None and d.divergent:
        text = reading(d, ctx.ficha_date)
    state = "differs" if bad else "ok" if obs and reference is not None else "na"
    return {
        "label": label, "unit": unit,
        "reference": MASK if personal and reference is not None else shown(reference)
        if reference is not None else None,
        "cells": {c: {**v, "value": " / ".join(v["values"])} for c, v in cells.items()},
        "reading": text or (COHERENT if state == "ok" else NO_DATA),
        "severity": finding.severity if finding else None,
        "state": state,
    }  # fmt: skip


def _finding(findings: list[Finding], rule: str, *prefixes: str) -> Finding | None:
    return next((f for f in findings if f.rule_id == rule
                 and (not prefixes or f.key.startswith(prefixes))), None)  # fmt: skip


def build(ctx: Context, findings: list[Finding] | None = None) -> dict[str, Any]:
    found = findings or []
    rows = []
    for label, key in (("Requerente", "id.requerente.nome"), ("Obra", "id.obra.designacao"),
                       ("Localização (concelho)", "id.local.concelho"),
                       ("Tipo de utilização", "ele.tipo_utilizacao")):  # fmt: skip
        finding = _finding(found, "COE-04", f"{key}|")
        if key == "ele.tipo_utilizacao" and finding is None:
            finding = _finding(found, "TIP-01", "use|")
        rows.append(_row(ctx, label, ctx.ficha_value(key), observations(ctx, key), equal(key),
                         finding, personal=key == "id.requerente.nome"))  # fmt: skip
    rows.append(
        _row(
            ctx,
            "Potência a alimentar",
            ctx.ficha_value(POWER),
            observations(ctx, POWER),
            same,
            _finding(found, "COE-05"),
            unit="kVA",
        )
    )
    for label, key in (("N.º de quadros", QTY_BOARDS), ("N.º de carregadores VE", QTY_EV)):
        reference, _ = coe_01.reference(ctx, key)
        obs = observations(ctx, key)
        if key == QTY_BOARDS:
            obs += coe_01._named_boards(ctx, coe_01._reference_names(ctx))
        rows.append(_row(ctx, label, reference, obs, same,
                         _finding(found, "COE-01", f"{key}|")))  # fmt: skip
    reference, _ = coe_01.luminaire_reference(ctx)
    rows.append(_row(ctx, "Tipos de luminárias", reference, observations(ctx, LUMINAIRE_TYPES),
                     same, _finding(found, "COE-01", f"{LUMINAIRE_TYPES}|")))  # fmt: skip
    cables = _finding(found, "COE-06")
    families = [Observation(o.piece, o.fact) for o in _all(ctx, CABLE)]
    rows.append(_cables(ctx, families, cables))
    rows.append(_row(ctx, "Potência FV", ctx.ficha_value("sys.fv") if isinstance(
        ctx.ficha_value("sys.fv"), int | float) else None, observations(ctx, PV_KWP), same,
        None, unit="kWp"))  # fmt: skip
    technician = [f for f in found if f.rule_id == "COE-04" and f.key.startswith("tec.")]
    tec_obs = observations(ctx, "tec.oet") + observations(ctx, "tec.nome")
    rows.append(_row(ctx, "Dados do técnico", None, tec_obs, same,
                     technician[0] if technician else None, personal=True))  # fmt: skip
    return {
        "reference": f"ficha-base rev. {ctx.revision.label}",
        "columns": [{"id": c, "label": label} for c, label in COLUMNS.items()],
        "rows": rows,
    }


def _all(ctx: Context, key: str) -> list[Observation]:
    """Every fact of the key (a piece may say several cables), one per value and piece."""
    seen: set[tuple[str, str]] = set()
    out = []
    for f in ctx.facts(key):
        piece = ctx.pieces.get(f.piece)
        if piece is None or (f.piece, str(f.value)) in seen:
            continue
        seen.add((f.piece, str(f.value)))
        out.append(Observation(piece, f))
    return out


def _cables(ctx: Context, obs: list[Observation], finding: Finding | None) -> dict[str, Any]:
    reference = sorted({str(o.fact.value) for o in obs if o.piece.kind == "CALC"})
    row = _row(ctx, "Cabos principais", ", ".join(reference) or None, obs,
               lambda a, b: str(a) in str(b).split(", "), finding)  # fmt: skip
    if finding is None and reference:
        row["reading"] = COHERENT
    return row
