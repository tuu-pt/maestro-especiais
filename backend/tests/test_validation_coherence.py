"""COE-01 to COE-06: how values are compared (task 4b). R1/R2 in test_validation_rules.py."""

import pytest

from app.validation.pieces import Fact
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
