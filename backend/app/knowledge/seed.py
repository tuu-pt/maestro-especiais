"""Seed the knowledge base from the reference projects in data/fixtures (Phase 3).

Idempotent: running it again replaces the occurrences and the evidence, and never touches what a
curator has decided (status, review note, aliases). Everything new is "proposed".

    python -m app.knowledge.seed            (FIXTURES_ROOT, default ../data/fixtures)

It also stores the reference MDJ/CTE split into sections (app.library.sources).
"""

import os
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import ficha_eletrotecnica
from app.ingest.detect import detect, fold
from app.knowledge import cables
from app.knowledge.regulations import seed_regulations
from app.knowledge.sources import SourceText, project_texts
from app.library import privacy
from app.models import (
    CableDesignation,
    CableEquivalence,
    CableOccurrence,
    Typology,
    TypologyTerm,
)

REFERENCE_PROJECTS = ("R1", "R2")

# Terms that should not appear in the documents of a typology (TIP-01), [A CONFIRMAR] pelo curador.
INCOMPATIBLE: dict[str, tuple[str, ...]] = {
    "moradia unifamiliar": (
        "apartamento", "fração", "condóminos", "condomínio", "partes comuns", "habitação coletiva",
    ),
    "biblioteca": ("moradia unifamiliar", "habitação unifamiliar", "apartamento", "fração"),
}  # fmt: skip


def default_root() -> Path:
    return Path(
        os.environ.get("FIXTURES_ROOT", Path(__file__).resolve().parents[3] / "data/fixtures")
    )


# ---------------------------------------------------------------- cables


def _occurrence(t: SourceText, d: cables.Designation) -> dict[str, Any]:
    return {
        "project": t.project, "source": t.source, "file": t.file, "locator": t.locator,
        "raw_text": d.raw[:160], "geometry": d.geometry,
    }  # fmt: skip


def seed_cables(db: Session, texts: Iterable[SourceText]) -> dict[str, int]:
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in texts:
        for d in cables.find(t.text):
            found[d.family].append(_occurrence(t, d))
    by_name = {c.canonical: c for c in db.scalars(select(CableDesignation))}
    for family, occurrences in found.items():
        row = by_name.get(family)
        if row is None:
            row = CableDesignation(
                canonical=family, kind=cables.kind(family), flexible=cables.flexible(family)
            )
            db.add(row)
            by_name[family] = row
        row.occurrences = [
            CableOccurrence(
                project_code=o["project"], source=o["source"], source_file=o["file"],
                locator=o["locator"][:120], raw_text=o["raw_text"], geometry=o["geometry"],
            )
            for o in occurrences
        ]  # fmt: skip
    db.flush()
    proposals = _equivalences(found)
    existing = {(e.a_id, e.b_id): e for e in db.scalars(select(CableEquivalence))}
    for (fa, fb), evidence in proposals.items():
        a, b = by_name[fa], by_name[fb]
        equivalence = existing.get((a.id, b.id))
        reason = (
            "No mesmo projeto, a mesma secção e o mesmo número de condutores aparecem com as duas "
            "designações em fontes diferentes (ex.: Tabela de Cálculo e MQT/LPU)."
        )
        if equivalence is None:
            db.add(CableEquivalence(a_id=a.id, b_id=b.id, reason=reason, evidence=evidence))
        else:
            equivalence.evidence = evidence  # the decision stays
    db.flush()
    return {"designations": len(found), "equivalences": len(proposals)}


def _equivalences(found: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, str], list[Any]]:
    """Proposed pairs: same project, same geometry, different families in different sources."""
    by_key: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for family, occurrences in found.items():
        for o in occurrences:
            if o["geometry"]:
                by_key[(o["project"], o["geometry"])].append((family, o))
    pairs: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for (project, geometry), items in by_key.items():
        for i, (fa, oa) in enumerate(items):
            for fb, ob in items[i + 1 :]:
                if oa["source"] == ob["source"] or not cables.may_be_equivalent(fa, fb):
                    continue
                key = (min(fa, fb), max(fa, fb))
                evidence = {"project": project, "geometry": geometry, "a": oa, "b": ob}
                if len(pairs[key]) < 5 and evidence not in pairs[key]:
                    pairs[key].append(evidence)
    return dict(pairs)


# ---------------------------------------------------------------- typologies and lexicon


def _typology_of(fixtures: Path, code: str, texts: list[SourceText]) -> tuple[str, list[Any]]:
    """The typology of a reference project, from the ficha eletrotécnica and the MDJ cover."""
    evidence: list[dict[str, str]] = []
    descricao = ""
    for path in sorted((fixtures / code).rglob("*.xlsm")):
        if detect(path.name, path.read_bytes()).kind == "ficha_eletrotecnica":
            values = {c.key: c for c in ficha_eletrotecnica.read(path.read_bytes()).values}
            for key in ("ele.descricao_imovel", "ele.classificacao", "ele.tipo_utilizacao"):
                if key in values:
                    c = values[key]
                    evidence.append({"project": code, "source": "Ficha eletrotécnica",
                                     "locator": c.source_ref, "text": str(c.value)})  # fmt: skip
            descricao = (
                fold(values["ele.descricao_imovel"].value)
                if "ele.descricao_imovel" in values
                else ""
            )
            break
    obra = next((t for t in texts if t.source == "MDJ" and fold(t.text).startswith("obra")), None)
    if obra:
        evidence.append({"project": code, "source": "MDJ (capa)", "locator": obra.locator,
                         "text": obra.text.strip()[:120]})  # fmt: skip
    folded_obra = fold(obra.text) if obra else ""
    if "unifamiliar" in descricao or "unifamiliar" in folded_obra:
        return "moradia unifamiliar", evidence
    if "biblioteca" in folded_obra:
        return "biblioteca", evidence
    return (folded_obra.split(":", 1)[-1].strip() or "tipologia por identificar"), evidence


def _term_pattern(term: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in fold(term).split()]
    return re.compile(r"(?<![\w])" + r"\s+".join(words) + r"(?:s|es)?(?![\w])")


def _snippet(text: str, start: int, end: int) -> str:
    left, right = max(0, start - 50), min(len(text), end + 50)
    return ("…" if left else "") + text[left:right].strip() + ("…" if right < len(text) else "")


def seed_lexicon(db: Session, fixtures: Path, texts_by_project: dict[str, list[SourceText]]) -> int:
    typologies = {t.name: t for t in db.scalars(select(Typology))}
    terms = 0
    for code, texts in texts_by_project.items():
        name, evidence = _typology_of(fixtures, code, texts)
        row = typologies.get(name)
        if row is None:
            row = Typology(name=name, evidence=[])
            db.add(row)
            typologies[name] = row
        row.evidence = [e for e in row.evidence if e.get("project") != code] + evidence
        db.flush()
        for term in INCOMPATIBLE.get(name, ()):
            pattern = _term_pattern(term)
            found = []
            for t in texts:
                if t.source not in ("MDJ", "CTE"):
                    continue
                spaced = " ".join(t.text.split())  # same offsets as its folded form
                m = pattern.search(fold(spaced))
                if m:
                    snippet = privacy.mask(_snippet(spaced, m.start(), m.end()))
                    found.append({"project": code, "source": t.source, "file": t.file,
                                  "locator": t.locator, "text": snippet})  # fmt: skip
            existing = next((x for x in row.terms if x.term == term), None)
            if existing is None:
                row.terms.append(TypologyTerm(term=term, evidence=found[:5]))
            else:
                others = [e for e in existing.evidence if e.get("project") != code]
                existing.evidence = others + found[:5]
            terms += 1
    db.flush()
    return terms


def seed_knowledge(
    db: Session, fixtures: Path, codes: Iterable[str] = REFERENCE_PROJECTS
) -> dict[str, int]:
    texts = {
        code: list(project_texts(fixtures, code)) for code in codes if (fixtures / code).is_dir()
    }
    result = seed_cables(db, (t for ts in texts.values() for t in ts))
    result["lexicon_terms"] = seed_lexicon(db, fixtures, texts)
    result["regulations"] = seed_regulations(db, [t for ts in texts.values() for t in ts])
    return result


def main() -> None:
    from app.config import get_settings
    from app.db import session_factory
    from app.library.seed import seed_blocks
    from app.library.sources import seed_sources
    from app.storage import ensure_bucket, get_store

    settings = get_settings()
    store = get_store(settings)
    if settings.s3_create_bucket:
        ensure_bucket(store.client, settings.s3_bucket)
    make = session_factory(settings.database_url)
    root = default_root()
    with make() as db:
        summary = seed_knowledge(db, root)
        summary |= seed_sources(db, store, root, REFERENCE_PROJECTS)
        summary |= seed_blocks(db, root, REFERENCE_PROJECTS)
        db.commit()
    print("Base de conhecimento semeada:", summary)


if __name__ == "__main__":
    main()
