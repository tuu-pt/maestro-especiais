"""COE-01 to COE-06: how values are compared (task 4b). R1/R2 in test_validation_rules.py."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.validation.context import Context
from app.validation.extract.files import TITLE_BLOCK_DATE, date_drawings
from app.validation.extract.text import LUMINAIRE_TYPES, luminaire_fact
from app.validation.normalize import month_year, shown_date
from app.validation.pieces import Fact, Piece, PieceData
from app.validation.rules import coe_01, coe_02
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


@pytest.mark.parametrize(
    ("written", "iso"),
    [("JUNHO 2026", "2026-06"), ("Março de 2026", "2026-03"), ("janeiro/2026", "2026-01"),
     ("06/2026", "2026-06"), ("01/26", "2026-01"), ("13/2026", None), ("Coimbra", None)],
)  # fmt: skip
def test_the_month_of_a_title_block(written: str, iso: str | None) -> None:
    assert month_year(written) == iso


def test_dates_are_shown_the_portuguese_way() -> None:
    assert shown_date("2026-03") == "março de 2026"
    assert shown_date("2026-10-06") == "06/10/2026"


def _drawings(title_block: list[str], confirmed: datetime) -> Context:
    piece = Piece("DRAWINGS", "DRAWINGS", "file", "", date="2026-10-06")  # uploaded today
    facts = [Fact(TITLE_BLOCK_DATE, d, "DRAWINGS", {}) for d in title_block]
    facts.append(Fact("id.obra.designacao", "Moradia MBERAL", "DRAWINGS", {}))
    data = {"DRAWINGS": PieceData(facts=facts)}
    date_drawings([piece], data)
    revision: Any = SimpleNamespace(confirmed_at=confirmed)
    ficha: Any = {"id.obra.designacao": SimpleNamespace(value="Biblioteca")}
    return Context(None, None, revision, {"DRAWINGS": piece}, data, ficha)  # type: ignore[arg-type]


def test_the_drawings_are_dated_by_their_title_block() -> None:
    ctx = _drawings(["MAIO 2026", "JUNHO 2026"], datetime(2026, 5, 20, tzinfo=UTC))
    [finding] = coe_02.check(ctx)

    assert ctx.pieces["DRAWINGS"].date == "2026-06"  # the latest month, not the upload day
    assert ctx.pieces["DRAWINGS"].date_source == "carimbadura"
    assert finding.message == (
        "Peças desenhadas (de junho de 2026 pela carimbadura) é posterior à ficha-base "
        "(confirmada a 20/05/2026) e diverge em «Designação da obra»."
    )


def test_drawings_of_the_month_of_the_ficha_are_not_more_recent() -> None:
    assert coe_02.check(_drawings(["JUNHO 2026"], datetime(2026, 6, 3, tzinfo=UTC))) == []
    # uploaded after the ficha, but drawn before it: not a more recent source
    assert coe_02.check(_drawings(["ABRIL 2026"], datetime(2026, 6, 3, tzinfo=UTC))) == []
