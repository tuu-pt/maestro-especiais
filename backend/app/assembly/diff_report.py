"""Difference between an assembled document and the original of a reference project (Phase 4).

    python -m app.assembly.diff_report <project code>   (make diff-report → docs/fase4-diff-R1.md)

For each entry of each block, the assembled text (the section's content, values resolved from the
ficha-base and the profile) is compared with the elements of the original the entry came from
(the .docx in data/fixtures, split as in Phase 3). Each difference gets one class:

- adaptive: text drafted by the agent (or still to draft): different by design;
- value: the ficha-base or the profile gives another value than the original (technician,
  date left to the technician, number format, missing in the ficha-base, ficha-base ≠ original);
- structure: a block of another reference project, inactive by its rule or with no text;
- defect: the literal text differs from the original. There must be none left unexplained.

The report never shows personal values: only keys, labels and masked excerpts.
"""

import difflib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.assemble import omitted
from app.assembly.values import ValueSource
from app.config import Settings
from app.drafting.draft import current, node_text
from app.ingest.detect import fold
from app.ingest.keys import KEYS
from app.library import privacy
from app.library.docx_blocks import split
from app.library.facts import DOC_KEYS
from app.library.placeholders import substitute
from app.library.sources import reference_documents
from app.models import Document, FichaRevision, Project, Section, TemplateBlock
from app.profiles import revision_profile

PLACEHOLDER = re.compile(r"\{\{v:([a-z0-9_.]+)\}\}")
# Value differences checked by hand on the fixtures (values not shown): project, key → why
EXPLAINED = {
    ("R1", "id.requerente.nome"): "o original usa a forma curta do nome; a ficha-base tem a "
    "designação completa do requerente",
    ("R1", "id.local.rua"): "a capa do original tem outra morada que a ficha eletrotécnica "
    "(com n.º de porta; pseudónimos diferentes, logo textos reais diferentes): a ficha-base é a "
    "fonte de verdade [A CONFIRMAR pela equipa]",
}
# Incoherences of the Annex C the assembly can touch, per project: (id, what, how to check)
KNOWN = {
    "R1": [
        ("C1", "MDJ com fios H07V-K; CTE e Tabela com H07V-U", "MDJ", "H07V-K"),
        ("C2", "CTE: «apartamento» numa moradia unifamiliar", "CTE", "apartamento"),
    ],
}


def fold_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def label(key: str) -> str:
    info = KEYS.get(key)
    return info.label_pt if info else DOC_KEYS.get(key, key)


def number(text: str) -> float | None:
    t = text.strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?", t):
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    return None


@dataclass
class Difference:
    section: str
    entry: int
    cls: str  # adaptive | value | structure | defect
    kind: str  # e.g. "perfil do técnico", "texto do agente"
    detail: str = ""


@dataclass
class Report:
    project: str
    doc_type: str
    sections: int = 0
    entries: int = 0
    equal: int = 0
    differences: list[Difference] = field(default_factory=list)
    known: list[tuple[str, str, str]] = field(default_factory=list)  # (id, what, state)
    issues: dict[str, int] = field(default_factory=dict)  # alerts of the agent's text, by rule

    def count(self, cls: str) -> int:
        return sum(1 for d in self.differences if d.cls == cls)


def value_kind(key: str, original: str, assembled: str | None, personal: bool) -> tuple[str, str]:
    """(kind, detail) of one value that differs. Personal values are never shown."""
    if key == "doc.data":
        return "data pelo técnico (P8)", "a data fica vazia: o técnico data e assina"
    if key.startswith(("tec.", "doc.")):
        note = " (C3: o n.º OET passa a vir só do perfil)" if key == "tec.oet" else ""
        return "perfil do técnico", f"{label(key)}: do perfil de quem confirmou a ficha{note}"
    if assembled is None:
        return "falta na ficha-base", f"{label(key)}: sem valor na ficha-base confirmada"
    a, b = number(original), number(assembled)
    if a is not None and b is not None and abs(a - b) < 1e-9:
        return "formato do número", f"{label(key)}: mesmo valor, outro formato"
    if fold(fold_space(original)) == fold(fold_space(assembled)):
        return "maiúsculas", f"{label(key)}: mesmo valor; o original está em maiúsculas"
    if personal:
        return "ficha-base ≠ original", f"{label(key)}: valor pessoal diferente (não mostrado)"
    shown = f"{privacy.mask(original)!r} → {privacy.mask(assembled)!r}"
    return "ficha-base ≠ original", f"{label(key)}: {shown} (a ficha-base é a fonte de verdade)"


def compare_entry(template: str, original: str, values: ValueSource
                  ) -> tuple[bool, list[tuple[str, str, str | None, bool]]]:  # fmt: skip
    """(literal text equal, [(key, original value, assembled value, personal)] that differ)."""
    template, original = fold_space(template), fold_space(original)
    parts = PLACEHOLDER.split(template)  # literal, key, literal, key, …
    pattern = "".join(
        re.escape(p) if i % 2 == 0 else "(.*?)" for i, p in enumerate(parts)
    )  # fmt: skip
    m = re.fullmatch(pattern, original, re.S)
    if m is None:
        return False, []
    out = []
    for key, got in zip(parts[1::2], m.groups(), strict=True):
        r = values.resolve(key)
        mine = None if r.missing else (r.text or "")
        differs = key == "doc.data" or mine is None or fold_space(mine) != fold_space(got)
        if differs and not (key == "doc.data" and not got.strip()):
            out.append((key, got, mine, r.personal))
    return True, out


def _original_sections(fixtures: Path, code: str, doc_type: str) -> dict[int, list[str]]:
    """Order of each section of the original → text of each of its body elements."""
    for kind, _, data in reference_documents(fixtures, code):
        if kind == doc_type:
            return {s.order: [substitute(e, []).text for e in s.elements]
                    for s in split(data).sections}  # fmt: skip
    raise FileNotFoundError(f"{doc_type} de {code} não encontrado em {fixtures}")


def _assembled_entries(section: Section) -> tuple[dict[int, str], list[str]]:
    """Entry → text with placeholders (not generated), and the generated paragraphs."""
    version = current(section)
    proposed = [v for v in section.versions if v.status == "proposed"]
    if version.author_type != "agent" and proposed:
        version = max(proposed, key=lambda v: v.number)
    entries: dict[int, list[str]] = {}
    generated: list[str] = []
    for node in version.content.get("content") or []:
        attrs = node.get("attrs") or {}
        if attrs.get("generated"):
            generated.append(node_text(node))
        elif node.get("type") in ("locked", "paragraph") and "entry" in attrs:
            if node.get("type") == "locked":
                lines = [
                    node_text({"content": p.get("content")}) for p in node.get("content") or []
                ]
                entries.setdefault(attrs["entry"], []).extend(lines)
            else:
                entries.setdefault(attrs["entry"], []).append(node_text(node))
    return {k: "\n".join(v) for k, v in entries.items()}, generated


def build(db: Session, settings: Settings, document: Document, fixtures: Path, code: str) -> Report:
    revision = db.get(FichaRevision, document.ficha_revision_id)
    assert revision is not None
    values = ValueSource.load(db, revision, revision_profile(db, settings, revision))
    originals = _original_sections(fixtures, code, document.type)
    report = Report(code, document.type)
    used_orders: set[int] = set()
    known = [k for k in KNOWN.get(code, []) if k[2] == document.type]
    known_state: dict[str, list[str]] = {cid: [] for cid, *_ in known}
    for section in sorted(document.sections, key=lambda s: s.order):
        block = db.get(TemplateBlock, section.block_id) if section.block_id else None
        if block is None:
            continue
        report.sections += 1
        ref = next((r for r in block.source_refs if r.get("project") == code), None)
        if block.kind == "index":
            if ref is not None:
                used_orders.add(int(ref["order"]))
            report.differences.append(Difference(
                section.title, -1, "structure", "índice",
                "campo do Word: é atualizado ao abrir o rascunho (updateFields)"))  # fmt: skip
            continue
        if ref is None:
            state = "inativa pela regra" if not section.active else "ativa, sem texto de " + code
            cls = "structure"
            if section.active and any(e.get("text") for e in block.body_template):
                state = "ativa, com texto de outro projeto"
            report.differences.append(Difference(section.title, -1, cls,
                                                 "bloco de outro projeto", state))  # fmt: skip
            continue
        used_orders.add(int(ref["order"]))
        elements = originals.get(int(ref["order"]), [])
        if not section.active:
            report.differences.append(Difference(
                section.title, -1, "defect", "secção do original desativada",
                section.active_reason or "desativada"))  # fmt: skip
            continue
        texts, generated = _assembled_entries(section)
        adaptive: list[int] = []
        adaptive_original: list[str] = []
        for i, e in enumerate(block.body_template):
            report.entries += 1
            idx = (e.get("units") or {}).get(code)
            if omitted(e):
                report.differences.append(Difference(
                    section.title, i, "structure", "imagem de um só projeto",
                    f"só em {e.get('project')}: não incluída (equipamento, Fase 7)"))  # fmt: skip
                continue
            if not idx and e["mode"] != "adaptive":
                report.differences.append(Difference(section.title, i, "structure",
                                                     "parágrafo de outro projeto"))  # fmt: skip
                continue
            original = "\n".join(elements[j] for j in idx or [] if j < len(elements))
            drafted = " ".join(generated)
            for cid, _, _, needle in known:
                if needle.lower() in original.lower():
                    if e["mode"] != "adaptive":
                        state = "mantém-se: texto fixo igual ao original (deteção na Fase 5)"
                    elif not generated:
                        state = "no texto adaptativo, ainda por gerar"
                    elif needle.lower() in drafted.lower():
                        state = "o agente repete-a (deteção na Fase 5)"
                    else:
                        state = "o agente não a repete no texto redigido"
                    known_state[cid].append(f"{section.title}: {state}")
            if e["mode"] == "adaptive":
                adaptive.append(i)
                adaptive_original.append(original)
                continue
            template = texts.get(i, e.get("text") or "")
            same, diffs = compare_entry(template, original, values)
            if not same:
                a, b = fold_space(original), fold_space(PLACEHOLDER.sub("…", template))
                report.differences.append(Difference(
                    section.title, i, "defect", "texto diferente do original",
                    _excerpt(a, b)))  # fmt: skip
            elif not diffs:
                report.equal += 1
            for key, got, mine, personal in diffs:
                kind, detail = value_kind(key, got, mine, personal)
                if (code, key) in EXPLAINED:
                    detail = f"{label(key)}: {EXPLAINED[(code, key)]}"
                report.differences.append(Difference(section.title, i, "value", kind, detail))
        if adaptive:
            report.differences.append(_adaptive(section, adaptive, adaptive_original, generated))
            for issue in _agent_version(section).issues if generated else []:
                rule = str(issue.get("rule", "?"))
                report.issues[rule] = report.issues.get(rule, 0) + 1
    for order, elements in originals.items():
        if order not in used_orders and any(t.strip() for t in elements):
            report.differences.append(Difference(f"secção {order} do original", -1, "defect",
                                                 "secção do original sem bloco"))  # fmt: skip
    for cid, what, _, _ in known:
        report.known.append(
            (cid, what, "; ".join(known_state[cid]) or "não encontrada no original")
        )
    return report


def _adaptive(section: Section, entries: list[int], originals: list[str],
              generated: list[str]) -> Difference:  # fmt: skip
    """One line per section: its adaptive entries against what the agent wrote."""
    where = ", ".join(map(str, entries))
    original = fold_space(" ".join(originals))
    if not generated:
        return Difference(section.title, entries[0], "adaptive", "por gerar", f"entradas {where}")
    if not original:
        return Difference(section.title, entries[0], "adaptive", "parágrafo de outro projeto",
                          f"entradas {where}: {len(generated)} parágrafo(s) do agente")  # fmt: skip
    drafted = fold_space(" ".join(generated))
    ratio = difflib.SequenceMatcher(None, original.split(), drafted.split()).ratio()
    state = "aceite" if current(section).author_type == "agent" else "proposta por aceitar"
    return Difference(section.title, entries[0], "adaptive", "texto do agente",
                      f"entradas {where}: {len(generated)} parágrafo(s), {state}; "
                      f"semelhança com o original {ratio:.0%}")  # fmt: skip


def _agent_version(section: Section) -> Any:
    agent = [v for v in section.versions if v.author_type == "agent"]
    return max(agent, key=lambda v: v.number)


def _excerpt(a: str, b: str, width: int = 60) -> str:
    """Where the two texts first differ, masked."""
    n = next((i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), min(len(a), len(b)))
    start = max(0, n - 20)
    return (f"original «{privacy.mask(a[start:start + width])}» · "
            f"montado «{privacy.mask(b[start:start + width])}»")  # fmt: skip


CLASSES = {
    "adaptive": "Texto adaptativo",
    "value": "Valor da ficha-base ou do perfil",
    "structure": "Estrutura (índice e blocos de outro projeto)",
    "defect": "Defeito",
}


def markdown(reports: list[Report]) -> str:
    out = [
        "# Fase 4 · Diferenças entre a montagem e o original de R1",
        "",
        "Gerado por `make diff-report` (`app/assembly/diff_report.py`) a partir da stack de",
        "desenvolvimento: R1 carregado de `data/fixtures`, ficha-base confirmada, MDJ e CTE",
        "montados com a biblioteca proposta e os adaptativos redigidos pelo agente. Cada entrada",
        "de cada bloco é comparada com os elementos do original de onde veio.",
        "Não mostra valores pessoais.",
        "",
        "| Documento | Secções | Entradas | Iguais | Adaptativo | Valor | Estrutura | Defeito |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        out.append(f"| {r.doc_type} | {r.sections} | {r.entries} | {r.equal} | "
                   f"{r.count('adaptive')} | {r.count('value')} | {r.count('structure')} | "
                   f"**{r.count('defect')}** |")  # fmt: skip
    out += [
        "",
        "Classes: **texto adaptativo** (redigido pelo agente: diferente por natureza; a semelhança",
        "é alta porque o arquivo inclui o próprio R1, num projeto novo não), **valor** (a",
        "ficha-base ou o perfil do técnico dão outro valor, ou falta o valor), **estrutura**",
        "(índice atualizado pelo Word e blocos de outro projeto, desativados pelas regras ou sem",
        "texto) e",
        "**defeito** (texto literal diferente do original, sem explicação). Os alertas do texto do",
        "agente (NUM-01: números fora de marcador, em geral distâncias e valores regulamentares",
        "copiados das fontes) ficam na versão para o técnico confirmar; a regra não é relaxada.",
    ]
    for r in reports:
        out += ["", f"## {r.doc_type}", ""]
        if r.issues:
            alerts = ", ".join(f"{rule}: {n}" for rule, n in sorted(r.issues.items()))
            out += [f"Alertas no texto do agente: {alerts}.", ""]
        if r.known:
            out += ["**Incoerências conhecidas (Anexo C)**", "", "| # | O quê | Na montagem |",
                    "|---|---|---|"]  # fmt: skip
            out += [f"| {cid} | {what} | {state} |" for cid, what, state in r.known]
            out.append("")
        for cls, title in CLASSES.items():
            rows = [d for d in r.differences if d.cls == cls]
            if not rows:
                continue
            out += [f"### {title} ({len(rows)})", "", "| Secção | Entrada | Tipo | Detalhe |",
                    "|---|---|---|---|"]  # fmt: skip
            for d in rows:
                entry = "—" if d.entry < 0 else str(d.entry)
                detail = d.detail.replace("|", "\\|")
                out.append(f"| {d.section} | {entry} | {d.kind} | {detail} |")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    from app.config import get_settings
    from app.db import session_factory

    code = sys.argv[1] if len(sys.argv) > 1 else "R1"
    settings = get_settings()
    fixtures = Path(os.environ.get(
        "FIXTURES_ROOT", Path(__file__).resolve().parents[3] / "data/fixtures"))  # fmt: skip
    with session_factory(settings.database_url)() as db:
        project = db.scalars(select(Project).where(Project.code == code)
                             .order_by(Project.created_at.desc())).first()  # fmt: skip
        if project is None:
            raise SystemExit(f"Projeto {code} não existe na base de dados.")
        reports = []
        for doc_type in ("MDJ", "CTE"):
            document = db.scalars(select(Document).where(
                Document.project_id == project.id, Document.type == doc_type)
                .order_by(Document.created_at.desc())).first()  # fmt: skip
            if document is not None:
                reports.append(build(db, settings, document, fixtures, code))
        sys.stdout.write(markdown(reports))


if __name__ == "__main__":
    main()
