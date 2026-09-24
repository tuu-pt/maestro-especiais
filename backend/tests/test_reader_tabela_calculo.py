from decimal import Decimal
from typing import Any

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


# The TUU template of R1 and R2: headers with line breaks and units, the codes of each column
# spelled out, and a second header line under "TIPO C" where the power is.
TUU_HEADER = [
    None, "Origem", "Destino", "TIPO C", None, None, None, None, None,
    "TIPO\nF (Fusível)\nD (Disjuntor)", "IB\n[A]\n\n", "In\n[A]\n\n", "I∆n\n[mA]",
    "Iz do cabo\n[A]\n\n", "I2\n[A]\n\n", "1,45 Iz\n[A]\n\n", "Canalização", None,
    "COMPRIMENTO\n[m]", "Q.D.T Troço\n[%]", "Q.D.T MONTANTE\n[%]", "Q.D.T TOTAL\n[%]",
    "Imped Troço\n[Ω]", "PdC\n[kA]", "CORTE GERAL\nJUSANTE [A]", None,
    "MONOPOLAR (MON)\nMULTIPOLAR (MUL)", "AO AR  ESTEIRA (EST)\nENTERRADO (ENT)\nEMBEBIDO (TUB)",
    "1=MONOFÁSICO 3=TRIFÁSICO", "ISOLAMENTO", "Cu=Cobre\nAl=Aluminio", "Mét Refª RTIEBT",
    "Quadro Calc RTIEBT",
]  # fmt: skip
TUU_SUBHEADER = [
    None, None, None, "Nº de Quadros \nTipo", "Norma [kVA]\n(S=√3xUxIB)", "Tensão \nNominal (U)",
    "Socorro [kVA]", "Segurança [kVA]", "TOTAL INSTALADO",
]  # fmt: skip
TUU_ENTRY = [
    None, "Portinhola", "Q.E.G.", 1, 200, 400, None, None, 200, "F", 250, 250, None, 347.17,
    504, 503.4, "XAV 4x1x185mm²", None, 25, 0.49, "-", 0.49, None, 6, None, None, "MON", "ENT",
    3, "XLPE", "Cu", "D1", "52-C3",
]  # fmt: skip


def test_tuu_template_with_a_two_line_header() -> None:
    rows: list[list[Any]] = [
        ["QUADRO ELÉTRICO"],
        TUU_HEADER,
        TUU_SUBHEADER,
        ["ENTRADA DE ENERGIA"],
        TUU_ENTRY,
    ]
    result = tc.read(factories.workbook_bytes({"Folha1": rows}))

    assert result.warnings == []
    entry = result.circuits[0]
    assert entry.source_ref == "Folha1!linha 5" and entry.section == "ENTRADA DE ENERGIA"
    assert entry.fields == {
        "origin": "Portinhola", "destination": "Q.E.G.", "kva": Decimal("200"),
        "voltage_v": Decimal("400"), "protection_type": "F", "ib_a": Decimal("250"),
        "in_a": Decimal("250"), "iz_a": Decimal("347.17"), "i2_a": Decimal("504"),
        "iz145_a": Decimal("503.4"), "cable_raw": "XAV 4x1x185mm²", "section_mm2": Decimal("185"),
        "length_m": Decimal("25"),
        "vd_section_pct": Decimal("0.49"), "vd_total_pct": Decimal("0.49"),
        "breaking_capacity_ka": Decimal("6"), "pole_type": "MON", "installation": "ENT",
        "phases": 3, "insulation": "XLPE", "conductor": "Cu", "ref_method": "D1",
        "rtiebt_table": "52-C3",
    }  # fmt: skip
    values = {c.key: c.value for c in result.values}
    assert values["ele.potencia_alimentar_kva"] == 200 and values["ele.entrada"] == "Trif"


def test_a_data_row_right_after_the_header_is_not_a_second_header_line() -> None:
    rows = [factories.CALC_HEADER, *factories.CALC_ROWS[1:]]  # no section row in between
    result = tc.read(factories.workbook_bytes({"Tabela": rows}))
    assert result.circuits[0].source_ref == "Tabela!linha 2"


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


@pytest.mark.parametrize(
    ("cable", "section"),
    [
        ("RV-K 4x16mm²", "16"),
        ("3x H07V-U 10mm²", "10"),
        ("XAV 4x1x185mm²", "185"),
        ("RZ1-K (AS) 5G10mm2", "10"),
        ("XZ1(frt,zh) 4x16", "16"),
        ("H07V-U 3G1,5", "1.5"),
        ("XZ1(frt,zh) 4x1x70mm²+1G35mm²", "70"),  # the phase, not the protective conductor
    ],
)
def test_phase_section_is_read_from_the_cable(cable: str, section: str) -> None:
    assert tc.cable_section(cable) == Decimal(section)


def test_cable_without_section_gives_none() -> None:
    assert tc.cable_section("cabo a definir") is None
