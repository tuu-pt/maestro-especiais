"""Blocks of the CTE of R1 and R2: general conditions fixed, equipment slots (Phase 3, task 7).

The round trip of both CTE is in test_library_docx_blocks; the leak test and the rules on R1/R2
run over the MDJ and the CTE blocks together (test_library_blocks, test_library_rules).
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.library.seed import seed_blocks
from app.library.sources import seed_sources
from app.models import TemplateBlock
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
GENERAL = "ele.cte.condicoes_tecnicas_gerais"
SPECIAL = "ele.cte.condicoes_tecnicas_especiais"


@pytest.fixture
def cte(db: Session, store: ObjectStore) -> dict[str, TemplateBlock]:
    if not (FIXTURES / "R1").is_dir() or not (FIXTURES / "R2").is_dir():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))
    rows = db.scalars(select(TemplateBlock).where(TemplateBlock.doc_type == "CTE"))
    return {b.key: b for b in rows}


def modes(b: TemplateBlock) -> set[str]:
    return {e["mode"] for e in b.body_template}


def test_every_section_of_both_cte_is_a_proposed_block(cte: dict[str, TemplateBlock]) -> None:
    ordered = sorted(cte.values(), key=lambda b: b.order)

    assert len(ordered) == 53
    assert [b.kind for b in ordered[:2]] == ["cover", "index"] and ordered[-1].kind == "signature"
    assert all(b.status == "proposed" for b in ordered)
    assert ordered[-1].mode == ordered[0].mode == "parametric"


def test_general_conditions_are_fixed(cte: dict[str, TemplateBlock]) -> None:
    general = {k: b for k, b in cte.items() if k.startswith(GENERAL)}

    assert set(general) == {
        GENERAL, f"{GENERAL}.introducao", f"{GENERAL}.caracteristicas_dos_materiais_e_equipamentos",
        f"{GENERAL}.ensaios_de_rececao_de_instalacao", f"{GENERAL}.omissoes",
    }  # fmt: skip
    for key, b in general.items():
        if key != f"{GENERAL}.introducao":
            assert b.mode == "fixed", key
    # wording that differs in R2 is kept from R1, with a note for the curator
    tests = general[f"{GENERAL}.ensaios_de_rececao_de_instalacao"]
    assert any("condições gerais, a confirmar" in (e["note"] or "") for e in tests.body_template)
    # the only paragraph not fixed identifies the project (its type, address and requerente)
    intro = general[f"{GENERAL}.introducao"]
    [adaptive] = [e for e in intro.body_template if e["mode"] == "adaptive"]
    assert "Tem valores do projeto" in adaptive["note"]
    assert set(adaptive["units"]) == {"R1", "R2"}
    # the RTIEBT paragraph, split into lines in R2, is the same text: fixed
    fixed = [e for e in intro.body_template if e["mode"] == "fixed" and e["text"]]
    assert any("RTIEBT" in e["text"] and set(e["units"]) == {"R1", "R2"} for e in fixed)


def slots(b: TemplateBlock) -> list[dict[str, Any]]:
    return list(b.equipment_slots)


def test_equipment_slots_are_marked(cte: dict[str, TemplateBlock]) -> None:
    server = cte[f"{SPECIAL}.servidor_knx"]

    assert slots(server)
    for slot in slots(server):
        entry = server.body_template[slot["entry"]]
        assert set(slot["reasons"]) <= {"ou equivalente", "marca/modelo"}
        assert slot["projects"] == sorted(entry["units"])
    assert any("ou equivalente" in s["reasons"] for b in cte.values() for s in slots(b))
    assert any("marca/modelo" in s["reasons"] for b in cte.values() for s in slots(b))
    # no slot outside the special conditions' equipment (not in the cover, the general part…)
    for key, b in cte.items():
        if key.startswith(GENERAL) or b.kind != "block":
            assert slots(b) == [], key
    # a slot is a place, never the equipment itself: no text is kept for it
    assert all(set(s) == {"entry", "reasons", "projects"} for b in cte.values() for s in slots(b))


def test_mdj_blocks_have_no_equipment_slots(db: Session, cte: dict[str, TemplateBlock]) -> None:
    mdj = db.scalars(select(TemplateBlock).where(TemplateBlock.doc_type == "MDJ"))
    assert all(b.equipment_slots == [] for b in mdj)


def test_rules_of_the_cte(cte: dict[str, TemplateBlock]) -> None:
    assert cte[f"{SPECIAL}.servidor_knx"].activation_rule == 'any bom.designation ~ "KNX"'
    assert (
        cte[f"{SPECIAL}.videoporteiro"].activation_rule == 'any bom.designation ~ "videoporteiro"'
    )
    assert cte[f"{SPECIAL}.inversor"].activation_rule == "sys.fv.present"
    assert cte[f"{SPECIAL}.quadros_eletricos"].activation_rule == "true"
