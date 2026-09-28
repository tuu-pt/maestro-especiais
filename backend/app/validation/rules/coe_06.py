"""COE-06 (SPEC 9): cable designations that differ after normalisation by the dictionary.

The reference is the Tabela de Cálculo (the source of ele.cabos). The written pieces (MDJ, CTE)
are compared with it together, and the MQT/LPU on their own (the quantities write the cables
their own way; C1 in R1: the MQT has H07V-K too) [A CONFIRMAR].

- Same type, one rigid and one flexible (H07V-U vs H07V-K): different cables, critical (C1).
- A designation with no approved equivalence with the reference: warning, ask the curator (C9);
  "proposed" equivalences of Phase 3 only say so in the evidence.
Earth conductors (earth and equipotential sections, articles about earth) are not compared: the
Tabela does not list them.
"""

import re
from collections import defaultdict

from app.ingest.detect import fold
from app.knowledge.cables import canonical_family, flexible, kind
from app.validation.compare import BOM, WRITTEN, location, where_label
from app.validation.context import Context
from app.validation.core import ASK_CURATOR, OPEN_EDITOR, Finding, Rule
from app.validation.extract.text import CABLE
from app.validation.likely import Divergence, Observation, reading
from app.validation.pieces import Fact, Piece

EARTH = re.compile(r"terra|equipotencia|condutores_de_protecao|condutor de protecao|electrodo")
GROUPS = (("escritas", WRITTEN), ("quantidades", BOM))


def base(family: str) -> str:
    return re.sub(r"-[UKRF]$", "", family.split("(")[0].strip().upper())


def _earth(fact: Fact) -> bool:
    """Earth conductors: earth sections and articles, or a single green-yellow core (1G16)."""
    where = f"{fact.locator.get('section', '')} {fold(fact.note or '')}"
    return bool(EARTH.search(where)) or bool(re.search(r"(?<!\d)1G\d", fact.shown or ""))


def _equivalences(ctx: Context) -> dict[frozenset[str], str]:
    out: dict[frozenset[str], str] = {}
    for e in ctx.cable_equivalences:
        out[frozenset((e.a.canonical, e.b.canonical))] = e.status
    for d in ctx.cables:
        if d.status == "approved":
            for alias in d.aliases or []:
                out[frozenset((d.canonical, canonical_family(str(alias))))] = "approved"
    return out


def check(ctx: Context) -> list[Finding]:
    reference = {f.value for f in ctx.facts(CABLE) if ctx.pieces[f.piece].kind == "CALC"}
    if not reference:
        return []
    known = {d.canonical for d in ctx.cables}
    equivalence = _equivalences(ctx)
    out = []
    for group, kinds in GROUPS:
        found: dict[str, list[tuple[Piece, Fact]]] = defaultdict(list)
        for f in ctx.facts(CABLE):
            piece = ctx.pieces[f.piece]
            if piece.kind in kinds and not _earth(f):
                found[f.value].append((piece, f))
        for family, where in sorted(found.items()):
            if family in reference:
                continue
            status = {r: equivalence.get(frozenset((family, r))) for r in reference}
            if "approved" in status.values():
                continue
            pieces = list({p.ref: p for p, _ in where}.values())
            names = ", ".join(p.name for p in pieces)
            written = sorted({f.shown or family for _, f in where})
            rigid = [r for r in sorted(reference) if base(r) == base(family)
                     and None not in (flexible(r), flexible(family))
                     and flexible(r) != flexible(family)]  # fmt: skip
            same_kind = [r for r in sorted(reference) if kind(r) == kind(family)]
            if not rigid and not same_kind:
                continue  # nothing of its kind in the Tabela to compare with
            if rigid:
                r = rigid[0]
                agreeing = [Observation(p, f) for p, f in _having(ctx, kinds, r)]
                divergent = [Observation(p, f) for p, f in where]
                text = reading(Divergence(r, agreeing, divergent), ctx.ficha_date)
                what = "fio" if kind(family) == "fio" else "cabo"
                message = (
                    f"Designação de cabos diferente: {names} indica {family} e a Tabela "
                    f"de Cálculo indica {r} ({what} flexível vs rígido: cabos diferentes)."
                )
                severity = "critical"
                actions = [OPEN_EDITOR]
            else:
                proposed = [r for r, s in status.items() if s == "proposed"]
                text = "Pedir equivalência ao curador."
                state = ("há uma equivalência proposta, por aprovar" if proposed
                         else "a designação não está no dicionário" if family not in known
                         else "sem equivalência no dicionário")  # fmt: skip
                message = (
                    f"Designação de cabos diferente: {names} indica {family}; a Tabela "
                    f"de Cálculo indica {', '.join(same_kind)} ({state})."
                )
                severity = "warning"
                actions = [ASK_CURATOR, OPEN_EDITOR]
                r = proposed[0] if proposed else same_kind[0]
            first_piece, first_fact = where[0]
            out.append(RULE.finding(
                message, key=f"{group}|{family}|{r}", severity=severity,
                location=location(first_piece, first_fact),
                evidence={"family": family, "written": written, "reference": sorted(reference),
                          "compared_with": r, "equivalence": status.get(r),
                          "pieces": [{"piece": p.ref, "piece_name": p.name, "where": where_label(f),
                                      "value": f.shown or family} for p, f in where][:12]},
                likely_reading=text, actions=actions,
            ))  # fmt: skip
    return out


def _having(ctx: Context, kinds: tuple[str, ...], family: str) -> list[tuple[Piece, Fact]]:
    out = []
    seen: set[str] = set()
    for f in ctx.facts(CABLE):
        piece = ctx.pieces[f.piece]
        if f.value == family and piece.kind in kinds and piece.ref not in seen and not _earth(f):
            seen.add(piece.ref)
            out.append((piece, f))
    return out


RULE = Rule("COE-06", "coherence", "critical", "Designação de cabos diferente", check)
