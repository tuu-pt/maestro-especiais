"""COE-04 (SPEC 9): identification different between pieces (C3, C7).

- Requerente, obra, localização and type of use, compared with the ficha-base: the likely
  reading of SPEC 9. A piece that differs in two or more identification fields (a value the
  ficha-base has, or one left empty where the piece usually has it) is read as reused from
  another project (C7).
- The technician (name, OET, CC), compared between the pieces: the ficha-base does not have it;
  the reading is to confirm with the technician's profile (C3), and the evidence says which
  pieces agree with the profile, without showing any value.

Personal values are compared here, in the backend, and every evidence is masked.
"""

import re
from collections.abc import Callable
from typing import Any

from app.ingest.consolidate import comparable
from app.ingest.detect import fold
from app.ingest.keys import KEYS
from app.validation.compare import compare, evidence, location, observations
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, OPEN_FICHA, Finding, Rule
from app.validation.extract.text import personal
from app.validation.likely import Observation, reading
from app.validation.pieces import Piece

IDENTIFICATION = {
    "id.requerente.nome": "requerente",
    "id.obra.designacao": "designação da obra",
    "id.local.rua": "rua",
    "id.local.freguesia": "freguesia",
    "id.local.concelho": "concelho",
    "ele.tipo_utilizacao": "tipo de utilização",
}
TECHNICIAN = {"tec.nome": "nome do técnico", "tec.oet": "n.º de membro OET",
              "tec.cc": "cartão de cidadão do técnico"}  # fmt: skip
# The fields each kind of piece usually has: an empty one counts as a difference (C7)
CARRIES = {
    "FICHA_ELE": {"id.requerente.nome", "id.local.rua", "id.local.freguesia",
                  "id.local.concelho", "ele.tipo_utilizacao"},
    "IDENTIFICACAO": {"id.requerente.nome", "id.local.rua", "id.local.freguesia",
                      "id.local.concelho", "ele.tipo_utilizacao"},
    "TERMO": {"id.requerente.nome", "id.local.rua", "id.local.freguesia", "id.local.concelho"},
}  # fmt: skip
REUSED = "{name} reaproveitada de outro projeto ({n} campos de identificação diferentes)."


STOP = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na", "no"}


def _words(key: str, value: Any) -> str:
    folded = comparable(key, value) if key in KEYS else fold(str(value))
    return re.sub(r"[^a-z0-9]+", " ", str(folded)).strip()


def equal(key: str) -> Callable[[Any, Any], bool]:
    """Same words, or one is a shorter form of the other: "MBERAL" in the title block and
    "Moradia unifamiliar - MBERAL" on the cover; the first and last names on the cover and the
    full name in the ficha; the street without the door number [A CONFIRMAR]."""

    def same_words(a: Any, b: Any) -> bool:
        wa, wb = _words(key, a), _words(key, b)
        if wa == wb:
            return True
        if key == "ele.tipo_utilizacao":
            return False
        sa, sb = set(wa.split()) - STOP, set(wb.split()) - STOP
        shorter = min(sa, sb, key=len)
        distinctive = any(len(w) >= 5 for w in shorter)
        return bool(shorter) and distinctive and (sa <= sb or sb <= sa)

    return same_words


def reused(ctx: Context) -> dict[str, int]:
    """Pieces that differ from the ficha-base in two or more identification fields."""
    if "reused" in ctx.memo:
        return ctx.memo["reused"]  # type: ignore[no-any-return]
    count: dict[str, int] = {}
    for key in IDENTIFICATION:
        ref = ctx.ficha_value(key)
        obs = observations(ctx, key)
        having = {o.piece.ref for o in obs}
        others = bool(having)
        for o in obs:
            if ref is not None and not equal(key)(o.fact.value, ref):
                count[o.piece.ref] = count.get(o.piece.ref, 0) + 1
        for piece in ctx.pieces.values():
            if key in CARRIES.get(piece.kind, set()) and piece.ref not in having and others:
                count[piece.ref] = count.get(piece.ref, 0) + 1  # empty where others say it
    ctx.memo["reused"] = {ref: n for ref, n in count.items() if n >= 2}
    return ctx.memo["reused"]  # type: ignore[no-any-return]


def reuse_reading(ctx: Context, piece: Piece) -> str | None:
    n = reused(ctx).get(piece.ref)
    return REUSED.format(name=piece.name, n=n) if n else None


def identification(ctx: Context) -> list[Finding]:
    out = []
    for key, label in IDENTIFICATION.items():
        ref = ctx.ficha_value(key)
        obs = observations(ctx, key)
        if ref is None or not obs:
            continue
        d = compare(ref, obs, equal(key))
        if not d.divergent:
            continue
        text = reading(d, ctx.ficha_date)
        if len(d.pieces) == 1:
            text = reuse_reading(ctx, d.pieces[0]) or text
        names = ", ".join(dict.fromkeys(o.piece.name for o in d.divergent))
        out.append(RULE.finding(
            f"Identificação diferente ({label}): {names} não coincide(m) com a ficha-base.",
            key=f"{key}|" + ",".join(sorted(p.ref for p in d.pieces)),
            location=location(d.divergent[0].piece, d.divergent[0].fact),
            evidence={**evidence(ctx, ref, "ficha-base", obs, d.divergent,
                                 personal=personal(key)), "field": label},
            likely_reading=text,
            suggested_fix="Corrigir a peça ou confirmar a ficha-base.",
            actions=[OPEN_EDITOR, OPEN_FICHA],
        ))  # fmt: skip
    return out


def technician(ctx: Context) -> list[Finding]:
    out = []
    profile = ctx.memo.get("profile", {})
    for key, label in TECHNICIAN.items():
        obs = observations(ctx, key)
        groups: dict[str, list[Observation]] = {}
        for o in obs:
            groups.setdefault(_words(key, o.fact.value), []).append(o)
        if len(groups) < 2:
            continue
        agree = [o.piece.name for o in obs
                 if profile.get(key) and equal(key)(o.fact.value, profile[key])]  # fmt: skip
        by_value = sorted(groups.values(), key=len, reverse=True)
        sets = " vs ".join(", ".join(o.piece.name for o in g) for g in by_value)
        out.append(RULE.finding(
            f"Dados do técnico diferentes ({label}): {sets}.",
            key=f"{key}|" + "|".join(",".join(sorted(o.piece.ref for o in g)) for g in by_value),
            location=location(by_value[-1][0].piece, by_value[-1][0].fact),
            evidence={**evidence(ctx, None, "perfil do técnico", obs, [], personal=True),
                      "groups": [[o.piece.name for o in g] for g in by_value],
                      "profile_agrees_with": agree if profile.get(key) else None,
                      "field": label},
            likely_reading="Confirmar com o perfil do técnico.",
            suggested_fix="Confirmar o valor no perfil do técnico e corrigir as peças que "
            "divergem.",
            actions=[OPEN_EDITOR],
        ))  # fmt: skip
    return out


def check(ctx: Context) -> list[Finding]:
    return identification(ctx) + technician(ctx)


RULE = Rule("COE-04", "coherence", "critical", "Identificação diferente entre peças", check)
