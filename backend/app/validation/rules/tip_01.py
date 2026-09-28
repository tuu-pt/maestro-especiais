"""TIP-01 (SPEC 9): text incompatible with the type of building, or names of another project.

- The lexicon of Phase 3 (proposed until the curator decides): the typology of the project is
  the one whose name is in the description of the work (designation, name, building type); its
  incompatible terms are searched in the MDJ and the CTE (C2: "apartamento" in a detached house).
- The type of use of the ficha eletrotécnica (and of the identification) must match the work the
  written pieces describe (C7: "Escritório" for a library) [A CONFIRMAR: the table USES].
- Requerente, work and street of the other projects of the archive, in this project's pieces.
Comparisons are folded text, in the backend; the evidence is masked.
"""

import re

from app.ingest.detect import fold
from app.validation.compare import excerpt, location, observations, paragraph_location
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, OPEN_FICHA, Finding, Rule
from app.validation.pieces import MASK
from app.validation.rules.coe_04 import reuse_reading

# DGEG type of use → words the description of the work must have [A CONFIRMAR]
USES = {
    "habitacao": ("habitac", "moradia", "apartamento", "residenc", "vivenda", "fogo"),
    "escritorio": ("escritorio", "servicos administrativos"),
    "comercio": ("comerci", "loja"),
    "industria": ("industri", "fabrica", "oficina"),
    "armazem": ("armazem", "armazen"),
    "restauracao": ("restaura", "cafe", "bar "),
    "hotelaria": ("hotel", "hostel", "alojamento"),
    "ensino": ("escola", "ensino", "universidade", "infancia"),
    "saude": ("hospital", "clinica", "saude"),
}
DESCRIBING = ("introducao", "classificacao")
INHERITED = "Texto herdado de outro projeto."
OWN = ("id.requerente.nome", "id.obra.designacao", "id.local.rua")


def _words(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", fold(text)) + " "


def description(ctx: Context) -> str:
    parts = [ctx.project.name or "", ctx.project.building_type or ""]
    parts += [str(f.value) for f in ctx.facts("id.obra.designacao")]
    parts.append(str(ctx.ficha_value("id.obra.designacao") or ""))
    parts += [p.text for p in ctx.paragraphs("MDJ", "CTE")
              if any(d in p.section_key for d in DESCRIBING)]  # fmt: skip
    return _words(" ".join(parts))


def lexicon(ctx: Context) -> list[Finding]:
    text = description(ctx)
    typologies = [t for t in ctx.typologies if t.status != "rejected"
                  and _words(t.name).strip() and _words(t.name) in text]  # fmt: skip
    out = []
    for typology in typologies:
        terms = [t.term for t in typology.terms if t.status != "rejected"]
        for p in ctx.paragraphs("MDJ", "CTE"):
            if p.section_kind != "block":
                continue
            words = _words(p.text)
            for term in terms:
                if _words(term) not in words:
                    continue
                piece = ctx.pieces[p.piece]
                m = re.search(re.escape(fold(term)), fold(p.text))
                start = m.start() if m else 0
                out.append(RULE.finding(
                    f"{piece.name} · {p.section_title}: «{term}» não é compatível com "
                    f"«{typology.name}».",
                    key=f"term|{p.piece}|{p.section_key}|{p.index}|{fold(term)}",
                    location=paragraph_location(ctx, p),
                    evidence={"term": term, "typology": typology.name,
                              "excerpt": excerpt(ctx, p.text, start, start + len(term)),
                              "lexicon_status": typology.status},
                    likely_reading=INHERITED,
                    suggested_fix="Rever o parágrafo: foi escrito para outro tipo de edifício.",
                    actions=[OPEN_EDITOR],
                ))  # fmt: skip
    return out


def uses(ctx: Context) -> list[Finding]:
    text = description(ctx)
    out = []
    for o in observations(ctx, "ele.tipo_utilizacao", ["FICHA_ELE", "IDENTIFICACAO"]):
        use = re.sub(r"[^a-z]", "", fold(o.fact.value))
        words = USES.get(use)
        if not words or any(w in text for w in words):
            continue
        described = sorted(k for k, ws in USES.items() if k != use and any(w in text for w in ws))
        out.append(RULE.finding(
            f"{o.piece.name}: o tipo de utilização «{o.fact.value}» não corresponde à obra "
            "descrita nas peças escritas.",
            key=f"use|{o.piece.ref}|{use}", location=location(o.piece, o.fact),
            evidence={"value": o.fact.value, "expected_words": list(words),
                      "described_uses": described},
            likely_reading=reuse_reading(ctx, o.piece) or f"Erro provável {o.piece.in_label}.",
            suggested_fix="Confirmar o tipo de utilização com o técnico e corrigir a peça.",
            actions=[OPEN_FICHA],
        ))  # fmt: skip
    return out


def other_projects(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    # a name that is also this project's own identification is not another project's
    own = {_words(str(ctx.ficha_value(k))) for k in OWN if ctx.ficha_value(k)}
    names = [(c, k, v) for c, k, v in ctx.other_projects_names
             if len(v.strip()) >= 6 and _words(v) not in own]  # fmt: skip
    if not names:
        return out
    for p in ctx.paragraphs("MDJ", "CTE"):
        words = _words(p.text)
        for code, key, value in names:
            if _words(value) not in words:
                continue
            piece = ctx.pieces[p.piece]
            personal = key != "id.obra.designacao"
            out.append(RULE.finding(
                f"{piece.name} · {p.section_title}: tem um nome do projeto {code} do arquivo.",
                key=f"name|{p.piece}|{p.section_key}|{p.index}|{code}|{key}",
                location=paragraph_location(ctx, p),
                evidence={"project": code, "field": key, "value": MASK if personal else value,
                          "excerpt": ctx.mask(excerpt(ctx, p.text).replace(value, MASK))},
                likely_reading=INHERITED, actions=[OPEN_EDITOR],
            ))  # fmt: skip
    for f in ctx.facts("id.requerente.nome"):
        piece = ctx.pieces[f.piece]
        for code, key, value in names:
            if key == "id.requerente.nome" and _words(value) == _words(str(f.value)):
                out.append(RULE.finding(
                    f"{piece.name}: o requerente é o do projeto {code} do arquivo.",
                    key=f"requerente|{f.piece}|{code}", location=location(piece, f),
                    evidence={"project": code, "field": key, "value": MASK},
                    likely_reading=reuse_reading(ctx, piece) or INHERITED,
                    actions=[OPEN_FICHA, OPEN_EDITOR],
                ))  # fmt: skip
    return out


def check(ctx: Context) -> list[Finding]:
    return lexicon(ctx) + uses(ctx) + other_projects(ctx)


RULE = Rule("TIP-01", "coherence", "critical", "Texto incompatível com a tipologia", check)
