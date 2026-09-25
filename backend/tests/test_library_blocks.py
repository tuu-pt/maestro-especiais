"""Blocks proposed from the MDJ of R1 and R2, paragraph by paragraph (Phase 3, task 3)."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.library import privacy
from app.library.docx_blocks import w
from app.library.facts import Fact, text_fact
from app.library.placeholders import substitute
from app.library.seed import ficha_values, project_docs, seed_blocks
from app.library.sources import seed_sources
from app.models import ArchiveChunk, SourceSection, TemplateBlock
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
HAVE_FIXTURES = (FIXTURES / "R1").is_dir() and (FIXTURES / "R2").is_dir()
PLACEHOLDER = re.compile(r"\{\{v:[a-z0-9_.]+\}\}")
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
SUPPLY = "instalacao_de_alimentacao_distribuicao_e_medida_de_energia"


# ---------------------------------------------------------------- placeholders in the OOXML


BOLD = "<w:rPr><w:b/></w:rPr>"


def paragraph(*runs: tuple[str, bool]) -> Any:
    body = "".join(
        f"<w:r>{BOLD if bold else ''}<w:t xml:space='preserve'>{text}</w:t></w:r>"
        for text, bold in runs
    )
    return etree.fromstring(f"<w:p xmlns:w='{w('x')[1:-2]}'>{body}</w:p>")


def power() -> Fact:
    return Fact("ele.potencia_alimentar_kva", "34,5 kVA",
                re.compile(r"(?<![\d,.])(34[,.]5)(?=\s*kVA\b)"))  # fmt: skip


def test_a_value_split_across_runs_keeps_the_first_run_formatting() -> None:
    p = paragraph(("potência de ", False), ("34", True), (",5", False), (" kVA.", False))

    sub = substitute(p, [power()])

    assert sub.text == "potência de {{v:ele.potencia_alimentar_kva}} kVA."
    assert sub.keys == ["ele.potencia_alimentar_kva"]
    runs = sub.element.findall(w("r"))
    assert runs[1].find(w("t")).text == "{{v:ele.potencia_alimentar_kva}}"
    assert runs[1].find(f"{w('rPr')}/{w('b')}") is not None  # the bold run of "34"
    assert runs[2].find(w("t")).text == ""
    assert p.findall(w("r"))[1].find(w("t")).text == "34"  # the original is untouched


def test_longest_value_wins_and_scope_breaks_ties() -> None:
    concelho = text_fact("id.local.concelho", "Coimbra")
    local = text_fact("doc.local", "Coimbra", "signature")
    assert concelho and local
    p = paragraph(("Coimbra, junho de 2026", False))

    assert substitute(p, [concelho, local]).text.startswith("{{v:id.local.concelho}}")
    assert substitute(p, [concelho, local], "signature").text.startswith("{{v:doc.local}}")


def test_privacy_patterns() -> None:
    text = ("Ana, ana@mail.pt, NIF 123456789, Tel. 912 345 678, 3000-123 Coimbra, "
            "Rua Nova 5, Membro OET: 12345, 3 de junho de 2026")  # fmt: skip
    kinds = {h.kind for h in privacy.find(text)}
    assert {"email", "nif", "phone", "postal_code", "address", "dgeg_oet", "date"} <= kinds
    assert "ana@mail.pt" not in privacy.mask(text)
    assert privacy.find("IP65, IK08, 16A-250V, secção 801.5, EN 12464-1, 230/400 V") == []
    assert privacy.find("{{v:id.local.cp}} {{v:id.local.concelho}}") == []


# ---------------------------------------------------------------- blocks of R1 and R2


@pytest.fixture
def seeded(db: Session, store: ObjectStore) -> dict[str, int]:
    if not HAVE_FIXTURES:
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    return seed_blocks(db, FIXTURES, ("R1", "R2"))


def block(db: Session, key: str) -> TemplateBlock:
    return db.scalars(select(TemplateBlock).where(TemplateBlock.key == f"ele.mdj.{key}")).one()


def entries(b: TemplateBlock, mode: str | None = None) -> list[dict[str, Any]]:
    return [e for e in b.body_template if mode is None or e["mode"] == mode]


def test_every_section_of_both_mdj_is_a_proposed_block(db: Session, seeded: dict[str, int]) -> None:
    blocks = db.scalars(select(TemplateBlock).order_by(TemplateBlock.order)).all()

    assert seeded["blocks"] == len(blocks) == 41
    assert all(b.status == "proposed" and b.doc_type == "MDJ" for b in blocks)
    assert [b.kind for b in blocks[:2]] == ["cover", "index"] and blocks[-1].kind == "signature"
    assert {b.mode for b in blocks} == {"fixed", "parametric", "adaptive"}
    # the order merges both documents: RPC (R2) after legislação, before características
    keys = [b.key for b in blocks]
    assert (
        keys.index("ele.mdj.regulamento_dos_produtos_de_construcao_rpc")
        == keys.index("ele.mdj.legislacao_e_normas") + 1
    )


def test_ip_ik_tables_are_fixed(db: Session, seeded: dict[str, int]) -> None:
    b = block(db, "caracteristicas_dos_equipamentos_em_funcao_das_influencias_externas")

    assert b.mode == "fixed" and b.locked_ooxml
    tables = [e for e in entries(b) if e["ooxml"] and e["ooxml"].startswith("<w:tbl")]
    assert len(tables) == 3 and all(e["mode"] == "fixed" for e in tables)
    assert all(set(e["units"]) == {"R1", "R2"} for e in tables)
    # the IK table has another header in R2: R1's is kept and the curator is told
    assert any("Diferente em R2" in (e["note"] or "") for e in tables)
    assert "Diferente em R2: fica a de R1 (a confirmar)." in b.notes


def test_power_of_r1_is_parametric_with_the_power_key(db: Session, seeded: dict[str, int]) -> None:
    b = block(
        db, "instalacao_de_alimentacao_distribuicao_e_medida_de_energia.alimentacao_de_energia"
    )

    [power_entry] = entries(b, "parametric")
    assert power_entry["keys"] == ["ele.potencia_alimentar_kva"]
    assert "{{v:ele.potencia_alimentar_kva}} kVA" in power_entry["text"]
    assert (
        "34,5" not in power_entry["ooxml"]
        and "{{v:ele.potencia_alimentar_kva}}" in power_entry["ooxml"]
    )
    assert (
        power_entry["units"] == {"R1": [5]} and power_entry["single_source"]
    )  # R2 has no such paragraph
    assert "ele.potencia_alimentar_kva" in b.required_keys


def test_cover_and_signature_are_parametric_without_personal_data(
    db: Session, seeded: dict[str, int]
) -> None:
    cover, signature = block(db, "capa"), block(db, "assinatura")

    assert cover.mode == signature.mode == "parametric"
    assert {"id.requerente.nome", "id.local.rua", "id.obra.designacao"} <= set(cover.required_keys)
    assert set(signature.required_keys) >= {
        "doc.local", "doc.data", "tec.nome", "tec.titulo", "tec.cc", "tec.oet",
        "tec.codigo_verificacao",
    }  # fmt: skip
    texts = [e["text"] for e in signature.body_template if e["text"]]
    assert "{{v:doc.local}}, {{v:doc.data}}" in texts
    assert "{{v:tec.nome}}, {{v:tec.titulo}}" in [t.strip() for t in texts]
    assert "Cc {{v:tec.cc}}" in texts and "Membro OET: {{v:tec.oet}}" in texts
    for text in texts:
        assert "Exemplo" not in text and not re.search(r"\d{4}", text)


def test_blocks_found_in_one_project_are_candidates(db: Session, seeded: dict[str, int]) -> None:
    for key, project in (
        ("instalacao_fotovoltaica", "R2"), ("carregamento_de_veiculos_eletricos", "R2"),
        ("sistema_automatico_de_detecao_de_incendio_sadi.matriz_de_incendio", "R2"),
        ("canalizacoes.canalizacoes_enterradas", "R1"),
        (f"{SUPPLY}.distribuicao_de_energia", "R1"),
    ):  # fmt: skip
        b = block(db, key)
        assert b.projects == [project]
        assert b.notes[0] == f"Bloco só em {project}: candidato, a regra de ativação decide."


def test_adaptive_blocks_keep_only_references(db: Session, seeded: dict[str, int]) -> None:
    b = block(db, "introducao")

    assert b.mode == "adaptive" and b.locked_ooxml is None
    [adaptive] = entries(b, "adaptive")
    assert adaptive["text"] is None and adaptive["ooxml"] is None
    assert set(adaptive["units"]) == {"R1", "R2"}
    assert b.archive_refs == ["arc:R1:ele.mdj.introducao", "arc:R2:ele.mdj.introducao"]
    chunks = db.scalars(select(ArchiveChunk).where(ArchiveChunk.block_key == b.key)).all()
    assert {c.ref for c in chunks} == set(b.archive_refs)
    r1 = next(c for c in chunks if c.doc.project_code == "R1")
    assert "{{v:id.local.rua}}" in r1.text and "Rua Exemplo" not in r1.text


def test_evidence_points_to_the_source_sections(db: Session, seeded: dict[str, int]) -> None:
    b = block(db, "dimensionamento_eletrico.quedas_de_tensao")

    assert b.mode == "fixed"  # the same text, split into other paragraphs in R2
    for ref in b.source_refs:
        section = db.get(SourceSection, ref["section_id"])
        assert section is not None and section.order == ref["order"]
        assert section.document.project_code == ref["project"]
    images = [e for e in entries(b) if e["ooxml"] and "<w:drawing" in e["ooxml"]]
    assert images and all(rid in b.ooxml_rels[e["project"]] for e in images
                          for rid in re.findall(r'r:embed="(rId\d+)"', e["ooxml"]))  # fmt: skip


def test_seeding_again_keeps_the_curator_decisions(db: Session, seeded: dict[str, int]) -> None:
    b = block(db, "legislacao_e_normas")
    b.status, b.review_note, b.title = "approved", "Revisto.", "Legislação (editado)"
    db.flush()

    again = seed_blocks(db, FIXTURES, ("R1", "R2"))

    assert again["blocks"] == seeded["blocks"] - 1  # the approved one is not rewritten
    db.refresh(b)
    assert (b.status, b.title) == ("approved", "Legislação (editado)")
    assert db.scalars(select(TemplateBlock)).all().__len__() == 41


# ---------------------------------------------------------------- no project or personal data


def _known_values() -> list[tuple[str, str]]:
    """Every value of R1/R2 a block must not keep: ficha, cover and signature."""
    values: list[tuple[str, str]] = []
    for code in ("R1", "R2"):
        ficha = ficha_values(FIXTURES, code)
        for key, value in ficha.items():
            if key.startswith("id.") and isinstance(value, str) and len(value) >= 4:
                values.append((key, value))
        for doc in project_docs_without_db(code):
            values += [(f.key, f.value) for f in doc if f.key.startswith(("id.", "tec.", "doc."))]
    return values


def project_docs_without_db(code: str) -> Iterator[list[Fact]]:
    from app.library.docx_blocks import split
    from app.library.facts import cover_facts, signature_facts
    from app.library.sources import reference_documents

    for _, _, data in reference_documents(FIXTURES, code):
        parts = split(data)
        yield cover_facts(parts.sections[0].text.splitlines()) + signature_facts(
            parts.sections[-1].text.splitlines()
        )


def _texts(b: TemplateBlock) -> Iterator[tuple[str, str]]:
    yield "title", b.title
    for note in b.notes:
        yield "note", note
    for n, e in enumerate(b.body_template):
        if e["text"]:
            yield f"entry {n}", e["text"]
        if e["ooxml"]:
            yield from _ooxml_texts(f"entry {n} ooxml", e["ooxml"])
    if b.locked_ooxml:
        yield from _ooxml_texts("locked_ooxml", b.locked_ooxml)


def _ooxml_texts(where: str, fragment: str) -> Iterator[tuple[str, str]]:
    root = etree.fromstring(
        f"<wrap xmlns:w='{w('x')[1:-2]}' xmlns:wp='{WP}' "
        "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
        "xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main' "
        "xmlns:pic='http://schemas.openxmlformats.org/drawingml/2006/picture' "
        "xmlns:w14='http://schemas.microsoft.com/office/word/2010/wordml' "
        "xmlns:mc='http://schemas.openxmlformats.org/markup-compatibility/2006' "
        "xmlns:v='urn:schemas-microsoft-com:vml' xmlns:o='urn:schemas-microsoft-com:office:office'>"
        + fragment + "</wrap>",
        etree.XMLParser(recover=True),
    )  # fmt: skip
    for p in root.iter(w("p")):
        text = "".join(t.text or "" for t in p.iter(w("t")))
        if text.strip():
            yield where, text
    for pr in root.iter(f"{{{WP}}}docPr"):
        yield f"{where} (imagem)", " ".join(pr.get(a) or "" for a in ("name", "descr", "title"))


def test_no_proposed_block_keeps_project_or_personal_data(
    db: Session, seeded: dict[str, int]
) -> None:
    known = _known_values()
    assert len(known) > 20
    leaks = []
    for b in db.scalars(select(TemplateBlock)):
        for where, text in _texts(b):
            bare = PLACEHOLDER.sub(" ", text)
            for hit in privacy.find(bare):
                leaks.append((b.key, where, hit.kind, hit.text))
            if re.search(r"\b[A-ZÀ-Ú][a-zà-ú]+ Exemplo\b", bare) or re.search(  # pseudonyms
                r"NOME\s*\|\s*ENG", bare, re.I
            ):
                leaks.append((b.key, where, "name", bare[:80]))
            folded = " ".join(bare.casefold().split())
            for key, value in known:
                v = " ".join(value.casefold().split())
                if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", folded):
                    leaks.append((b.key, where, key, value))
    for power in ("34,5 kVA", "180 kVA"):
        leaks += [(b.key, w_, "power", power) for b in db.scalars(select(TemplateBlock))
                  for w_, t in _texts(b) if power in PLACEHOLDER.sub(" ", t)]  # fmt: skip
    assert leaks == []


def test_archive_keeps_no_personal_data(db: Session, seeded: dict[str, int]) -> None:
    for chunk in db.scalars(select(ArchiveChunk)):
        bare = PLACEHOLDER.sub(" ", chunk.text)
        assert privacy.find(bare) == [], (chunk.ref, privacy.find(bare))
        assert not re.search(r"\b[A-ZÀ-Ú][a-zà-ú]+ Exemplo\b", bare), chunk.ref


def test_the_facts_of_each_project(db: Session, seeded: dict[str, int]) -> None:
    docs = project_docs(db, FIXTURES, "R1")
    keys = {f.key for f in docs["MDJ"].facts}
    assert {"ele.potencia_alimentar_kva", "id.local.rua", "id.requerente.nome", "doc.local",
            "tec.nome", "tec.cc", "tec.oet"} <= keys  # fmt: skip
    assert "ele.classificacao" not in keys  # a DGEG list value: ordinary words in the text
