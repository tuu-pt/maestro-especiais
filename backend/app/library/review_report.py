"""docs/revisao-curador.md: everything the curator has to review, with the evidence (Phase 3).

Generated from the proposals in the database (after make seed-library), never by hand:

    python -m app.library.review_report > ../docs/revisao-curador.md      (make curator-review)

Only what the library already keeps: placeholders, masked evidence, designations of cables,
references of the corpus. No personal data and no project values.
"""

from collections import Counter
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.library import privacy
from app.library.preview import label
from app.library.skeleton import EXPECTED_DIFFERENCES
from app.models import (
    CableDesignation,
    CableEquivalence,
    RegulationDoc,
    TemplateBlock,
    Typology,
)

MODES = {"fixed": "fixo", "parametric": "paramétrico", "adaptive": "adaptativo"}
STATUS = {"proposed": "proposto", "approved": "aprovado", "rejected": "rejeitado",
          "confirmed": "confirmado"}  # fmt: skip
LEGAL = {"in_force": "em vigor", "revoked": "revogado", "reference_only": "só referência"}


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _blocks(db: Session, doc_type: str) -> Iterator[str]:
    blocks = db.scalars(
        select(TemplateBlock)
        .where(TemplateBlock.doc_type == doc_type)
        .order_by(TemplateBlock.order)
    ).all()
    modes = Counter(b.mode for b in blocks)
    yield (f"{len(blocks)} blocos: {modes['fixed']} fixos, {modes['parametric']} paramétricos, "
           f"{modes['adaptive']} adaptativos. Estado: "
           + ", ".join(f"{n} {STATUS[s]}" for s, n in Counter(b.status for b in blocks).items())
           + ".")  # fmt: skip
    yield ""
    yield "| # | Bloco | Modo | Projetos | Regra de ativação | Estado |"
    yield "|---|---|---|---|---|---|"
    for b in blocks:
        projects = ", ".join(b.projects) or "esqueleto 8.3"
        title = ("↳ " if b.level == 2 else "") + b.title
        yield (f"| {b.order} | {_cell(title)} | {MODES[b.mode]} | {projects} | "
               f"`{_cell(b.activation_rule)}` | {STATUS[b.status]} |")  # fmt: skip
    yield ""
    yield f"#### O que pedir atenção no {doc_type}"
    yield ""
    for b in blocks:
        points = list(b.notes)
        single = [e for e in b.body_template if e.get("single_source")]
        if single:
            keys = sorted({k for e in single for k in e.get("keys") or []})
            points.append("Paramétrico com evidência de um só projeto: "
                          + ", ".join(_placeholder(k) for k in keys) + ".")  # fmt: skip
        if b.equipment_slots:
            reasons = Counter(r for s in b.equipment_slots for r in s["reasons"])
            points.append(f"{len(b.equipment_slots)} lugar(es) de equipamento de referência ("
                          + ", ".join(f"{r}: {n}" for r, n in reasons.items()) + ").")  # fmt: skip
        if not points:
            continue
        yield f"- **{b.title}** (`{b.key}`)"
        for point in dict.fromkeys(points):
            yield f"  - {point}"
    yield ""


def _placeholder(key: str) -> str:
    return "`{{v:" + key + "}}` (" + label(key) + ")"


def _differences() -> Iterator[str]:
    yield "| Bloco | Projeto | Porque a regra e o documento não coincidem |"
    yield "|---|---|---|"
    for (key, project), why in EXPECTED_DIFFERENCES.items():
        yield f"| `{key}` | {project} | {_cell(why)} |"
    yield ""


def _cables(db: Session) -> Iterator[str]:
    designations = db.scalars(select(CableDesignation).order_by(CableDesignation.canonical)).all()
    yield "| Designação | Tipo | Condutor | Onde aparece | Estado |"
    yield "|---|---|---|---|---|"
    for d in designations:
        where = Counter(f"{o.project_code} · {o.source}" for o in d.occurrences)
        flexible = "—" if d.flexible is None else ("flexível" if d.flexible else "rígido")
        yield (f"| `{d.canonical}` | {d.kind} | {flexible} | "
               + ", ".join(f"{k} ({n})" for k, n in sorted(where.items()))
               + f" | {STATUS[d.status]} |")  # fmt: skip
    yield ""
    yield "Equivalências propostas (nunca entre um fio rígido e um flexível):"
    yield ""
    for e in db.scalars(select(CableEquivalence)):
        yield f"- **`{e.a.canonical}` ≈ `{e.b.canonical}`** ({STATUS[e.status]}). {e.reason}"
        for ev in e.evidence[:3]:
            yield (f"  - {ev['project']}, secção {ev['geometry']}: «{ev['a']['raw_text']}» "
                   f"({ev['a']['source']}, {ev['a']['locator']}) e «{ev['b']['raw_text']}» "
                   f"({ev['b']['source']}, {ev['b']['locator']})")  # fmt: skip
    yield ""


def _lexicon(db: Session) -> Iterator[str]:
    for t in db.scalars(select(Typology).order_by(Typology.name)):
        where = "; ".join(f"{e['project']} · {e['source']}: «{privacy.mask(e['text'])}»"
                          for e in t.evidence)  # fmt: skip
        yield f"- **{t.name}** ({STATUS[t.status]}). Evidência: {where or '—'}"
        for term in t.terms:
            found = term.evidence
            if found:
                first = found[0]
                where_ = f"{first['project']} · {first['source']}"
                seen = (f"encontrado {len(found)} vez(es), ex.: {where_} "
                        f"· {first['locator']}: «{privacy.mask(first['text'])}»")  # fmt: skip
            else:
                seen = "não aparece nos documentos de referência"
            yield f"  - «{term.term}» ({STATUS[term.status]}): {seen}"
    yield ""


def _corpus(db: Session) -> Iterator[str]:
    yield "| Documento | Tipo | Âmbito | Citado em R1/R2 | Estado | Citável |"
    yield "|---|---|---|---|---|---|"
    for r in db.scalars(select(RegulationDoc).order_by(RegulationDoc.kind, RegulationDoc.title)):
        where = Counter(f"{f['project']} · {f['source']}" for f in r.found_in)
        sample = ", ".join(sorted(where))
        cited = f"{r.found_count} vez(es): {sample}" if r.found_count else "**não citado**"
        state = STATUS[r.review_status] + (f", {LEGAL[r.status]}" if r.status else "")
        note = " (só título e âmbito: direitos de autor)" if r.copyrighted else ""
        yield (f"| {_cell(r.title)} | {r.kind} | {_cell(r.scope)}{note} | {cited} | {state} | "
               f"{'sim' if r.citable else 'não'} |")  # fmt: skip
    yield ""


def _equipment(db: Session) -> Iterator[str]:
    from app.equipment import CATEGORIES
    from app.equipment.params import shown
    from app.models import Equipment, Requirement

    items = db.scalars(select(Equipment).order_by(Equipment.category, Equipment.code,
                                                  Equipment.name)).all()  # fmt: skip
    with_sheet = sum(1 for e in items if any(d.status == "current" for d in e.datasheets))
    yield (f"{len(items)} equipamentos de referência propostos dos CTE de R1 e R2; {with_sheet} "
           "com ficha técnica (data/fixtures/fichas-tecnicas). Os parâmetros lidos ficam por "
           "rever no ecrã G (EQP-01 só usa os revistos); a verificação de R1 com as fichas está "
           "em docs/fase7-fichas-R1.md.")  # fmt: skip
    yield ""
    yield ("| Categoria | Equipamento | Fabricante | Modelo / referência | «ou equivalente» "
           "| Ficha | Onde | Estado |")  # fmt: skip
    yield "|---|---|---|---|---|---|---|---|"
    for e in items:
        model = " · ".join(x for x in (e.code, e.model, e.reference) if x)
        where = ", ".join(sorted({s["project"] for s in e.sources}))
        equivalent = "sim" if e.or_equivalent else "**não**"
        sheet = next((d.file_name for d in e.datasheets if d.status == "current"), "—")
        yield (f"| {CATEGORIES.get(e.category, e.category)} | {_cell(e.name)} | "
               f"{_cell(e.manufacturer)} | {_cell(model)} | {equivalent} | {_cell(sheet)} "
               f"| {where} | {STATUS[e.status]} |")  # fmt: skip
    yield ""
    yield "Requisitos propostos dos CTE (aprovados com o bloco):"
    yield ""
    by_block: dict[str, list[str]] = {}
    for r in db.scalars(
        select(Requirement).order_by(Requirement.block_key, Requirement.param_name)
    ):
        whose = "do bloco" if r.equipment_id is None else "da linha"
        by_block.setdefault(r.block_key, []).append(
            f"{r.param_name} {r.operator} {shown(r.param_name, r.value)} ({whose})"
        )
    for key, needs in by_block.items():
        yield f"- `{key}`: " + "; ".join(needs)
    yield ""


def report(db: Session) -> str:
    lines = [
        "# Revisão do curador · Fase 3",
        "",
        "Gerado a partir das propostas da biblioteca (`make seed-library` e depois "
        "`make curator-review`). **Nada está aprovado**: tudo o que o agente extraiu dos projetos "
        "de referência R1 e R2 (anonimizados) fica «proposto» até o curador decidir no ecrã G · "
        "Base de conhecimento, com o papel Curador. Cada decisão fica na auditoria.",
        "",
        "O curador ainda não está designado (D7). Sem ele, a Fase 3 não fecha: o critério da "
        "SPEC 14 pede os esqueletos da secção 8.3 completos com blocos **aprovados**.",
        "",
        "## Como rever",
        "",
        "1. Ecrã G → Biblioteca de blocos: para cada bloco, ver os parágrafos (marcadores "
        "`{{v:…}}` realçados), a evidência de R1 e R2 lado a lado, a regra de ativação e a "
        "pré-visualização com a ficha de um projeto. Aprovar, editar (título, modo, regra, com "
        "justificação) ou rejeitar.",
        "2. Dicionário de cabos, Léxico de tipologias e Corpus regulamentar: aprovar ou rejeitar "
        "cada proposta; no corpus, confirmar o estado e a edição em vigor antes de marcar como "
        "citável.",
        "3. As decisões de método abaixo (marcadas [A CONFIRMAR]) valem para todos os blocos.",
        "",
        "## Decisões de método [A CONFIRMAR]",
        "",
        "- O modo de um bloco é o mais forte dos seus parágrafos "
        "(adaptativo > paramétrico > fixo).",
        "- Um marcador `{{v:chave}}` só é proposto quando R1 e R2 coincidem com a mesma chave no "
        "mesmo sítio; um parágrafo que só existe num projeto e tem valores da ficha fica "
        "paramétrico com a marca «evidência de um só projeto» (ex.: a potência de R1).",
        "- Valores trocados por marcadores: identificação (`id.*`), potências com «kVA» e tensão "
        "com «kV»; da capa e da assinatura, pelas etiquetas (requerente, localização, obra; local, "
        "data, técnico). Os valores das listas DGEG («Habitação», «Nova»…) ficam como texto: "
        "servem as regras.",
        "- Chaves novas, fora da ficha, resolvidas na Fase 4: `doc.local`, `doc.data` (vazio, P8), "
        "`tec.nome`, `tec.titulo`, `tec.cc`, `tec.oet`, `tec.codigo_verificacao`, `tec.email`, "
        "`tec.telefone`.",
        "- Tabelas e imagens (as fórmulas são imagens) nunca são adaptativas: quando diferem, fica "
        "a de R1 como fixa, com nota.",
        "- O mesmo texto partido noutros parágrafos, ou com outra pontuação final, conta como "
        "igual.",
        "- Condições técnicas gerais do CTE propostas como fixas: redação diferente fica com o "
        "texto de R1 e nota; só o parágrafo que identifica o projeto fica adaptativo.",
        "- O cabeçalho dos documentos tem o técnico, a data e a revisão: fica no pacote do "
        "documento de origem e terá de ser paramétrico na Fase 4.",
        "- Blocos adaptativos: o texto de cada projeto vai para o arquivo (marcadores no lugar dos "
        "valores, dados pessoais mascarados); o bloco guarda só a regra e as referências.",
        "- Equivalências de cabos só com evidência: mesmo projeto, mesma secção e número de "
        "condutores, fontes diferentes.",
        "",
        "## Biblioteca de blocos · MDJ",
        "",
        *_blocks(db, "MDJ"),
        "## Biblioteca de blocos · CTE",
        "",
        *_blocks(db, "CTE"),
        "## Regras de ativação: diferenças esperadas",
        "",
        "Sobre R1 e R2, as regras propostas reproduzem os blocos presentes nas MDJ e nos CTE, "
        "exceto aqui (os testes verificam que são as únicas):",
        "",
        *_differences(),
        "## Dicionário de cabos",
        "",
        *_cables(db),
        "## Léxico de tipologias (regra TIP-01)",
        "",
        *_lexicon(db),
        "## Corpus regulamentar (Anexo D)",
        "",
        "Só referências: título, âmbito e onde R1/R2 as citam. Tudo por confirmar e não citável. A "
        "pesquisa no texto integral (RegulationChunk) fica para mais tarde.",
        "",
        *_corpus(db),
        "## Equipamentos (Fase 7)",
        "",
        *_equipment(db),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    import sys

    from app.config import get_settings
    from app.db import session_factory

    with session_factory(get_settings().database_url)() as db:
        sys.stdout.buffer.write(report(db).encode("utf-8"))


if __name__ == "__main__":
    main()
