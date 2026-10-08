"""COE-01 (SPEC 9): the quantity of an element differs between the pieces and the ficha-base.

Boards, EV chargers and PV modules by quantity; luminaires by type (L1, L7, SNC…), since the CTE
lists the types without quantities. The reference is the ficha-base; when it has no value,
the source the ficha-base takes it from (SPEC 7.2: the Tabela de Cálculo, then the MQT/LPU),
and the evidence says so. A text that names the boards without saying how many is comparable
only when it names exactly the boards of the reference.

Critical when the MDJ or the CTE differs; a warning when only the MQT/LPU does. A value from the
ficha-base edited by hand in an assembled piece (screen D) is a COE-01 of its own.

Luminaires [A CONFIRMAR]: the reference is the MQT/LPU (the ficha-base has no luminaires); the
types of the MDJ/CTE are compared with its types, a variant with its type (L5.1, L5.2 → L5); a
type missing from one side is a warning (types are not quantities).
"""

from typing import Any

from app.validation.compare import (
    BOM,
    WRITTEN,
    board_count,
    compare,
    evidence,
    location,
    observations,
    shown,
)
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, OPEN_FICHA, Finding, Rule
from app.validation.extract.text import (
    BOARD_NAMES,
    LUMINAIRE_TYPES,
    QTY_BOARDS,
    QTY_EV,
    QTY_PV_MODULES,
)
from app.validation.likely import Observation, reading
from app.validation.normalize import same
from app.validation.pieces import Fact

ELEMENTS = {
    QTY_BOARDS: ("quadros elétricos", "ele.quadros"),
    QTY_EV: ("carregadores de veículos elétricos", "sys.ve"),
    QTY_PV_MODULES: ("módulos fotovoltaicos", "sys.fv"),
}
FALLBACK_SOURCES = ("CALC", "MQT", "LPU")


def reference(ctx: Context, key: str) -> tuple[Any, str]:
    ficha_key = ELEMENTS[key][1]
    value = ctx.ficha_value(ficha_key)
    if key == QTY_BOARDS and isinstance(value, list):
        return board_count(value), "ficha-base (quadros)"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value, "ficha-base"
    for kind in FALLBACK_SOURCES:
        obs = observations(ctx, key, [kind])
        if obs:
            name = obs[0].piece.name
            return obs[0].fact.value, f"ficha-base sem valor: {name} (fonte da ficha-base)"
    return None, "ficha-base sem valor"


def _named_boards(ctx: Context, reference_names: list[str] | None) -> list[Observation]:
    """Pieces that name the boards without counting them: comparable when the names agree."""
    counted = {o.piece.ref for o in observations(ctx, QTY_BOARDS)}
    out = []
    for f in ctx.facts(BOARD_NAMES):
        piece = ctx.pieces.get(f.piece)
        if piece is None or f.piece in counted or piece.kind not in WRITTEN:
            continue
        if reference_names and sorted(f.value) == sorted(reference_names):
            fact = Fact(QTY_BOARDS, len(f.value), f.piece, f.locator, shown=str(len(f.value)),
                        note="nomeia os mesmos quadros da ficha-base")  # fmt: skip
            out.append(Observation(piece, fact))
    return out


def _reference_names(ctx: Context) -> list[str] | None:
    from app.ingest import boards as board_names

    value = ctx.ficha_value("ele.quadros")
    if isinstance(value, list):
        return sorted({board_names.core(str(v)) for v in value if board_names.core(str(v))})
    obs = observations(ctx, BOARD_NAMES, ["CALC"])
    return list(obs[0].fact.value) if obs else None


def quantities(ctx: Context) -> list[Finding]:
    out = []
    for key, (label, _) in ELEMENTS.items():
        ref, ref_label = reference(ctx, key)
        obs = observations(ctx, key)
        if key == QTY_BOARDS:
            obs += _named_boards(ctx, _reference_names(ctx))
        if ref is None or not obs:
            continue
        d = compare(ref, obs)
        if not d.divergent:
            continue
        kinds = {o.piece.kind for o in d.divergent}
        severity = "critical" if kinds & set(WRITTEN) else "warning" if kinds <= set(BOM) else None
        first = d.divergent[0]
        out.append(RULE.finding(
            f"N.º de {label} diferente da referência ({shown(ref)}): "
            + "; ".join(f"{o.piece.name} {shown(o.fact.value)}" for o in d.divergent) + ".",
            key=f"{key}|" + ",".join(sorted(o.piece.ref for o in d.divergent)),
            severity=severity, location=location(first.piece, first.fact),
            evidence={**evidence(ctx, ref, ref_label, obs, d.divergent), "element": label},
            likely_reading=reading(d, ctx.ficha_date),
            suggested_fix="Corrigir a peça suspeita ou, se a ficha-base estiver errada, abrir "
            "uma nova revisão da ficha.",
            actions=[OPEN_EDITOR, OPEN_FICHA],
        ))  # fmt: skip
    return out


def luminaire_reference(ctx: Context) -> tuple[list[str] | None, str]:
    """The luminaire types of the MQT (or the LPU): the ficha-base has none."""
    for kind in BOM:
        obs = observations(ctx, LUMINAIRE_TYPES, [kind])
        if obs:
            return list(obs[0].fact.value), f"ficha-base sem valor: {obs[0].piece.name}"
    return None, "ficha-base sem valor"


def _difference(ref: list[str], value: list[str]) -> str:
    missing = [t for t in ref if t not in value]
    extra = [t for t in value if t not in ref]
    parts = ([f"sem {', '.join(missing)}"] if missing else []) + (
        [f"a mais {', '.join(extra)}"] if extra else []
    )
    return "; ".join(parts)


def luminaires(ctx: Context) -> list[Finding]:
    ref, ref_label = luminaire_reference(ctx)
    if ref is None:
        return []
    reference_piece = next(o.piece.ref for o in observations(ctx, LUMINAIRE_TYPES, BOM))
    obs = [o for o in observations(ctx, LUMINAIRE_TYPES) if o.piece.ref != reference_piece]
    d = compare(ref, obs)
    if not d.divergent:
        return []
    first = d.divergent[0]
    return [RULE.finding(
        f"Tipos de luminárias diferentes da referência ({shown(ref)}): "
        + "; ".join(f"{o.piece.name} {_difference(ref, list(o.fact.value))}"
                    for o in d.divergent) + ".",
        key=f"{LUMINAIRE_TYPES}|" + ",".join(sorted(o.piece.ref for o in d.divergent)),
        severity="warning", location=location(first.piece, first.fact),
        evidence={**evidence(ctx, ref, ref_label, obs, d.divergent), "element": "luminárias"},
        likely_reading=reading(d, ctx.ficha_date),
        suggested_fix="Acertar a lista de luminárias do CTE com os artigos do MQT/LPU (ou o "
        "contrário).",
        actions=[OPEN_EDITOR],
    )]  # fmt: skip


def edited_values(ctx: Context) -> list[Finding]:
    """Values of the ficha-base edited by hand in an assembled piece (SPEC 10.D)."""
    out = []
    for piece in ctx.of_kind(*WRITTEN):
        if piece.origin != "assembled":
            continue
        for f in ctx.data[piece.ref].facts:
            if f.note != "valor editado à mão":
                continue
            ref = ctx.ficha_value(f.key)
            if ref is not None and same(f.value, ref):
                continue
            obs = [Observation(piece, f)]
            out.append(RULE.finding(
                f"{piece.name} · {f.locator.get('section_title', '')}: o valor de «{f.key}» foi "
                "editado à mão e difere da ficha-base.",
                key=f"edited|{piece.ref}|{f.locator.get('anchor')}",
                location=location(piece, f),
                evidence=evidence(ctx, ref, "ficha-base", obs, obs, personal=f.personal),
                likely_reading=f"Erro provável {piece.in_label} (valor editado à mão).",
                suggested_fix="Repor o valor da ficha-base ou abrir uma nova revisão da ficha.",
                actions=[OPEN_EDITOR, OPEN_FICHA],
            ))  # fmt: skip
    return out


def check(ctx: Context) -> list[Finding]:
    return quantities(ctx) + luminaires(ctx) + edited_values(ctx)


RULE = Rule("COE-01", "coherence", "critical", "Quantidades diferentes entre peças", check)
