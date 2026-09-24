from decimal import Decimal

import factories
import pytest

from app.ingest import tabela_calculo as tc
from app.ingest.pipeline import ReaderError


def test_one_circuit_per_line_with_origin_and_section() -> None:
    result = tc.read(factories.tabela_calculo())

    assert [c.fields["destination"] for c in result.circuits] == [
        "Q.E.G.",
        "Q.P.1",
        "C1 Iluminação",
    ]
    assert [c.section for c in result.circuits] == ["ENTRADA DE ENERGIA", "EDIFÍCIO", "EDIFÍCIO"]
    assert result.circuits[0].source_ref == "Tabela!linha 3"
    assert result.warnings == []


def test_values_are_read_not_computed() -> None:
    entry = tc.read(factories.tabela_calculo()).circuits[0].fields

    assert entry["kva"] == Decimal("34.5")
    assert entry["i2_a"] == Decimal("100.8") and entry["iz145_a"] == Decimal("110.2")
    assert entry["cable_raw"] == "XZ1(frt,zh) 4x16"
    assert entry["installation"] == "ENT" and entry["pole_type"] == "MUL"
    assert entry["phases"] == 3 and entry["conductor"] == "Cu"
    assert "idn_ma" not in entry  # empty IΔn column


def test_columns_are_found_by_header_text_in_any_order() -> None:
    header = list(reversed(factories.CALC_HEADER))
    rows = [list(reversed(r)) if len(r) > 1 else r for r in factories.CALC_ROWS]

    result = tc.read(factories.tabela_calculo(header=header, rows=rows))

    assert result.circuits[0].fields["origin"] == "Portinhola"
    assert result.circuits[0].fields["iz_a"] == Decimal("76")


@pytest.mark.parametrize(
    ("header", "field"),
    [
        ("IΔn (mA)", "idn_ma"),
        ("I∆n", "idn_ma"),
        ("1,45·Iz (A)", "iz145_a"),
        ("1.45 x Iz", "iz145_a"),
        ("Iz (A)", "iz_a"),
        ("QDT Total (%)", "vd_total_pct"),
        ("Queda de tensão acumulada", "vd_total_pct"),
        ("Tensão (V)", "voltage_v"),
        ("Poder de corte (kA)", "breaking_capacity_ka"),
        ("Nº de pólos", "pole_type"),
        ("Condutor", "conductor"),
        ("Designação do cabo", "cable_raw"),
    ],
)
def test_header_synonyms(header: str, field: str) -> None:
    assert tc.match_column(header) == field


def test_unknown_columns_are_reported_not_ignored_silently() -> None:
    header = [*factories.CALC_HEADER, "Observações"]
    result = tc.read(factories.tabela_calculo(header=header))

    assert result.warnings == ["Coluna não reconhecida: «Observações»."]


def test_header_can_start_below_a_title_block() -> None:
    data = factories.workbook_bytes(
        {"Resumo": [["TABELA DE CÁLCULO"], [], factories.CALC_HEADER, *factories.CALC_ROWS]}
    )
    result = tc.read(data)
    assert result.circuits[0].source_ref == "Resumo!linha 5"


def test_ficha_base_candidates_come_from_the_first_line_and_the_boards() -> None:
    values = {c.key: (c.value, c.source_ref) for c in tc.read(factories.tabela_calculo()).values}

    assert values["ele.potencia_alimentar_kva"] == (34.5, "Tabela!linha 3")
    assert values["ele.entrada"][0] == "Trif"
    assert values["ele.quadros"][0] == ["Q.E.G.", "Q.P.1"]
    assert values["ele.cabos"][0] == ["XZ1(frt,zh) 4x16", "H07V-U 3G6", "H07V-U 3G1,5"]


def test_table_without_origin_and_destination_is_not_a_calc_table() -> None:
    with pytest.raises(ReaderError, match="ORIGEM / DESTINO"):
        tc.read(factories.mqt())
