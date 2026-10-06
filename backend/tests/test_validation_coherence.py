"""COE-01 to COE-06: how values are compared (task 4b). R1/R2 in test_validation_rules.py."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.validation.context import Context
from app.validation.extract.text import LUMINAIRE_TYPES, luminaire_fact
from app.validation.pieces import Fact, Piece, PieceData
from app.validation.rules import coe_01
from app.validation.rules.coe_04 import equal
from app.validation.rules.coe_06 import _earth, base


@pytest.mark.parametrize(
    ("key", "a", "b", "same"),
    [("id.obra.designacao", "MBERAL", "Moradia unifamiliar - MBERAL", True),
     ("id.obra.designacao", "Reabilitação da Biblioteca", "Requalificação da Biblioteca", False),
     ("id.requerente.nome", "Câmara Municipal de Cantanhede", "Município de Cantanhede", True),
     ("id.requerente.nome", "Ana Silva", "Ana Maria Costa Silva", True),
     ("id.requerente.nome", "Ana Silva", "Rui Costa", False),
     ("ele.tipo_utilizacao", "Escritório", "Escritórios e serviços", False),
     ("tec.oet", "12345", "12 345", False)],
)  # fmt: skip
def test_identification_is_compared_by_words(key: str, a: str, b: str, same: bool) -> None:
    assert equal(key)(a, b) is same


def test_cables_of_the_same_type_rigid_or_flexible_and_earth_conductors() -> None:
    assert base("H07V-U") == base("H07V-K") == "H07V"
    assert base("RZ1-K (AS)") == "RZ1"
    assert _earth(Fact("cabo", "XV-R", "p", {}, shown="XV-R 1G16mm²"))
    assert _earth(Fact("cabo", "H07V-U", "p", {"section": "rede_de_terras"}, shown="H07V-U"))
    assert not _earth(Fact("cabo", "XV", "p", {"section": "cabos_e_fios"}, shown="XV"))


def _context(**codes: list[str]) -> Context:
    pieces = {kind: Piece(kind, kind, "existing" if kind in ("MDJ", "CTE") else "file", "")
              for kind in codes}  # fmt: skip
    data = {kind: PieceData(facts=[luminaire_fact(c, kind, {}, "")]) for kind, c in codes.items()}
    revision: Any = SimpleNamespace(confirmed_at=None)
    return Context(None, None, revision, pieces, data)  # type: ignore[arg-type]


def test_luminaire_types_are_compared_with_the_bill_of_quantities() -> None:
    same = _context(CTE=["L1", "L5"], LPU=["L1", "L5.1", "L5.2"])
    [finding] = coe_01.luminaires(_context(CTE=["L1", "L2", "L9"], MQT=["L1", "L2", "L3"]))

    assert coe_01.luminaires(same) == []  # L5.1 and L5.2 are L5
    assert finding.severity == "warning" and finding.key == f"{LUMINAIRE_TYPES}|CTE"
    assert finding.message == (
        "Tipos de luminárias diferentes da referência (L1, L2, L3): "
        "CTE (existente) sem L3; a mais L9."
    )
    assert finding.likely_reading == "Erro provável no CTE."
    assert "quadros" not in finding.message  # the R1 control of the Annex C is about boards


def test_without_a_bill_of_quantities_the_luminaires_are_not_compared() -> None:
    assert coe_01.luminaires(_context(CTE=["L1"])) == []
