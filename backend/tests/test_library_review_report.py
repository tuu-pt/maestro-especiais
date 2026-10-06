"""docs/revisao-curador.md is generated from the proposals, with evidence and no personal data."""

import re
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.equipment.seed import seed_equipment
from app.knowledge.seed import seed_knowledge
from app.library import privacy
from app.library.review_report import report
from app.library.seed import seed_blocks
from app.library.sources import seed_sources
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
PLACEHOLDER = re.compile(r"\{\{v:[a-z0-9_.]+\}\}")


@pytest.fixture
def text(db: Session, store: ObjectStore) -> str:
    if not (FIXTURES / "R1").is_dir() or not (FIXTURES / "R2").is_dir():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_knowledge(db, FIXTURES)
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))
    seed_equipment(db)
    return report(db)


def test_it_covers_everything_the_curator_reviews(text: str) -> None:
    for heading in (
        "## Decisões de método [A CONFIRMAR]", "## Biblioteca de blocos · MDJ",
        "## Biblioteca de blocos · CTE", "## Regras de ativação: diferenças esperadas",
        "## Dicionário de cabos", "## Léxico de tipologias (regra TIP-01)",
        "## Corpus regulamentar (Anexo D)", "## Equipamentos (Fase 7)",
    ):  # fmt: skip
        assert heading in text
    assert "**Nada está aprovado**" in text
    assert "42 blocos:" in text and "53 blocos:" in text
    assert "C12:" in text  # the expected difference of the rules
    assert "**`RZ1-K (AS)` ≈ `XZ1(frt,zh)`**" in text
    assert "«apartamento» (proposto): encontrado" in text
    assert "Paramétrico com evidência de um só projeto: `{{v:ele.potencia_alimentar_kva}}`" in text
    assert "| Despacho n.º 1/2018 da DGEG |" in text and "**não citado**" in text
    assert "| Portinhola | Portinhola PBT Tri | Quitérios | +32470 | sim | R1 | proposto |" in text
    assert "icc_ka >= 25 kA (do bloco)" in text


def test_it_keeps_no_personal_data(text: str) -> None:
    bare = PLACEHOLDER.sub(" ", text)
    assert privacy.find(bare) == []
    assert not re.search(r"\b[A-ZÀ-Ú][a-zà-ú]+ Exemplo\b", bare)
