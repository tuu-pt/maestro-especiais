import factories
import pytest

from app.ingest import ficha_eletrotecnica as fe
from app.ingest.keys import info
from app.ingest.pipeline import ReaderError


def values(data: bytes) -> dict[str, object]:
    return {c.key: c.value for c in fe.read(data).values}


def test_every_mapped_cell_becomes_a_key_with_its_origin() -> None:
    result = fe.read(factories.ficha_eletrotecnica())

    assert result.source_type == "ficha_eletrotecnica"
    assert result.template_version == factories.FE_VERSION
    refs = {c.key: c.source_ref for c in result.values}
    assert refs["ele.potencia_alimentar_kva"] == "Ficha Eletrotecnica!R29"
    assert refs["id.requerente.nome"] == "Ficha Eletrotecnica!C5"
    assert len(refs) == len(fe.cell_maps()[factories.FE_VERSION].cells)


def test_numbers_are_read_as_numbers_even_when_typed_as_text() -> None:
    found = values(factories.ficha_eletrotecnica(R29="41,4", P29=34.5, Q29="0,8"))

    assert found["ele.potencia_alimentar_kva"] == 41.4
    assert found["ele.potencia_instalada_kva"] == 34.5
    assert found["ele.fator_simultaneidade"] == 0.8


def test_whole_numbers_stay_whole_and_text_is_trimmed() -> None:
    found = values(factories.ficha_eletrotecnica(Q5=999990013.0, M29="  Habitação  "))

    assert found["id.requerente.nif"] == "999990013"
    assert found["ele.tipo_utilizacao"] == "Habitação"


def test_empty_cells_create_no_value() -> None:
    found = values(factories.ficha_eletrotecnica(G16=None, C15="   "))  # as in R2 (case C7)

    assert "id.local.rua" not in found
    assert "id.local.freguesia" not in found


def test_personal_keys_are_flagged_in_the_catalogue() -> None:
    personal = {
        c.key for c in fe.read(factories.ficha_eletrotecnica()).values if info(c.key).personal
    }
    assert personal == {
        "id.requerente.nome",
        "id.requerente.nif",
        "id.requerente.morada",
        "id.requerente.email",
        "id.requerente.cp",
        "id.local.rua",
        "id.local.gps",
    }


def test_each_cell_is_the_one_next_to_its_label_in_the_template() -> None:
    found = values(factories.ficha_eletrotecnica())

    assert found["id.requerente.email"] == "requerente@example.com"  # J6, E-Mail:
    assert found["id.requerente.cp"] == "0000-001 Localidade de Teste"  # C8, C. Postal:
    assert found["id.local.freguesia"] == "Freguesia de Teste"  # C15
    assert found["id.local.concelho"] == "Concelho de Teste"  # M15
    assert found["id.local.distrito"] == "Distrito de Teste"  # Q15
    assert found["id.local.rua"] == "Rua de Teste"  # G16, Entrada principal (Lugar/Rua):
    assert found["id.local.gps"] == "0.000, -0.000"  # Q16
    # Not in the ficha: they come from other sources (MQT/LPU, manual).
    assert "id.obra.designacao" not in found and "id.local.cp" not in found
    assert "ele.contagem" not in found  # I44 is the total power of type C, not the metering


def test_unknown_template_version_stops_reading() -> None:
    with pytest.raises(ReaderError, match="novo mapa de células"):
        fe.read(factories.ficha_eletrotecnica(R45="FE_v.20250101"))


def test_missing_template_version_stops_reading() -> None:
    with pytest.raises(ReaderError, match="R45"):
        fe.read(factories.ficha_eletrotecnica(R45=None))


def test_blank_ficha_reads_with_a_warning() -> None:
    blank = {cell: None for cell in fe.cell_maps()[factories.FE_VERSION].cells}
    result = fe.read(factories.ficha_eletrotecnica(**blank))

    assert result.values == []
    assert result.warnings == ["A ficha eletrotécnica não tem nenhum valor preenchido."]


def test_every_mapped_key_exists_in_spec_7_2() -> None:
    for cell_map in fe.cell_maps().values():
        for key in cell_map.cells.values():
            assert info(key).group
