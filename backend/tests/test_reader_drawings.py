"""PDF of the drawings: index, title block of every page, pages; mirrored and repeated text."""

from typing import Any

import factories
import pytest
from conftest import Api

from app.ingest import drawings
from app.ingest.detect import detect
from app.ingest.pipeline import ReaderError

CODES = ["EL001", "EL002", "EL003"]


def by_key(reading: drawings.DrawingsReading) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for c in reading.result.values:
        out.setdefault(c.key, []).append(c)
    return out


def test_index_title_block_and_pages() -> None:
    reading = drawings.read(factories.drawings_set(CODES))

    assert reading.pages == 4 and reading.warnings == []
    assert reading.index[1] == {
        "codigo": "EL002",
        "titulo": "PLANTA 2",
        "data": "06/26",
        "revisao": None,
    }
    values = {k: v[0] for k, v in by_key(reading).items()}
    assert values["id.requerente.nome"].value == "Município de Teste"
    assert values["id.obra.designacao"].value == "Edifício de Teste"  # the address is not in it
    assert values["pd.carimbadura.fase"].value == "PROJETO DE EXECUÇÃO"
    assert values["pd.carimbadura.codigo"].value == "12345678"  # not "código" of the copyright
    assert values["pd.carimbadura.data"].source_ref == "PDF · págs. 1-4 · carimbadura"
    assert values["pd.n_paginas_pdf"].value == 4
    assert reading.sheets[2] == {"pagina": 3, "codigo": "EL002", "titulo": "PLANTA EL002"}


def test_the_index_and_the_pages_are_compared_by_sheet_code_c4() -> None:
    reading = drawings.read(factories.drawings_set(CODES, sheets=2))  # EL003 is not drawn
    check = drawings.index_check(reading.index, reading.sheets, reading.pages)
    assert check["missing_in_pdf"] == ["EL003"] and check["matches"] is False

    full = drawings.read(factories.drawings_set(CODES))
    assert drawings.index_check(full.index, full.sheets, full.pages)["matches"] is True


def test_el001_and_001_are_the_same_sheet() -> None:
    index = [{"codigo": "001"}, {"codigo": "002"}]
    sheets = [{"codigo": "000", "titulo": "ÍNDICE"}, {"codigo": "EL001"}, {"codigo": "EL002"}]
    assert drawings.index_check(index, sheets, 3)["matches"] is True


def test_title_blocks_that_disagree_give_one_candidate_per_value() -> None:
    pages = [
        factories.title_block("EL001", "PLANTA 1"),
        factories.title_block("EL002", "PLANTA 2", fase="PROJETO BASE"),
        factories.title_block("EL003", "PLANTA 3"),
    ]
    fases = by_key(drawings.read(factories.drawings_pdf(pages)))["pd.carimbadura.fase"]
    assert [(c.value, c.source_ref) for c in fases] == [
        ("PROJETO DE EXECUÇÃO", "PDF · págs. 1, 3 · carimbadura"),
        ("PROJETO BASE", "PDF · pág. 2 · carimbadura"),
    ]


def test_mirrored_and_repeated_text_is_dropped() -> None:
    block = factories.title_block("EL001", "PLANTA 1")
    extra: list[factories.Text] = [
        (1000, 382, "FORNO", True),
        (1000, 262, "Edifício de Teste", False),
    ]
    runs = drawings.page_runs_from(factories.drawings_pdf([block + extra]))
    texts = [r.text for r in runs]
    assert "FORNO" not in texts and "ONROF" not in texts
    assert texts.count("Edifício de Teste") == 1


def test_text_of_the_plan_under_the_title_block_is_not_a_value() -> None:
    # As in R2: room names and bus labels of the plan run under the title block.
    plan = [(1060, 240, "2.07 | Ludoteca", False), (1140, 344, "BUS DALI", False)]
    values = by_key(
        drawings.read(factories.drawings_pdf([[*factories.title_block("EL001", "P1"), *plan]]))
    )
    assert values["id.requerente.nome"][0].value == "Município de Teste"
    assert values["pd.carimbadura.fase"][0].value == "PROJETO DE EXECUÇÃO"


@pytest.mark.parametrize(
    ("rotation", "box", "expected"),
    [
        (0, (10, 800, 50, 830), (10, 12, 50)),
        (270, (10, 800, 50, 830), (12, 792, 42)),
        (90, (10, 800, 50, 830), (800, 10, 830)),
    ],
)
def test_rotated_pages_are_read_as_displayed(
    rotation: int, box: tuple[float, ...], expected: tuple[float, float, float]
) -> None:
    width, height = (842, 842)
    assert drawings._display(rotation, width, height, box) == expected


def test_a_pdf_without_index_is_read_with_a_warning() -> None:
    pages = [factories.title_block("EL001", "PLANTA 1"), factories.title_block("EL002", "PLANTA 2")]
    reading = drawings.read(factories.drawings_pdf(pages))
    assert reading.index == [] and "pd.indice" not in by_key(reading)
    assert reading.warnings == ["O PDF não tem folha de índice (EL001…): índice não lido."]


def test_only_pdfs_with_a_title_block_are_drawings() -> None:
    assert detect("EL.pdf", factories.drawings_set(CODES)).kind == "drawing_pdf"
    memoria = factories.drawings_pdf([[(60, 60, "MEMÓRIA DESCRITIVA E JUSTIFICATIVA", False)]])
    assert detect("MDJ.pdf", memoria).kind == "other"
    assert detect("EL.pdf", b"%PDF-1.4 broken").kind == "other"
    with pytest.raises(ReaderError, match="ilegível"):
        drawings.read(b"%PDF-1.4 broken")


# ---------------------------------------------------------------- through the API

pytestmark = pytest.mark.usefixtures("inline_ingestion")


def ficha_after(api: Api, *files: tuple[str, bytes]) -> dict[str, Any]:
    client = api.as_("redator")
    project_id = client.post("/api/projects", json={"code": "R9", "name": "Obra"}).json()["id"]
    for name, data in files:
        assert (
            client.post(
                f"/api/projects/{project_id}/files", files={"file": (name, data)}
            ).status_code
            == 202
        )
    body: dict[str, Any] = client.get(f"/api/projects/{project_id}/ficha").json()
    return body


def values(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {v["key"]: v for g in body["groups"] for v in g["values"]}


def test_the_ficha_shows_the_drawings_group_and_the_index_check(api: Api) -> None:
    body = ficha_after(api, ("EL.pdf", factories.drawings_set(CODES, sheets=2)))

    group = next(g for g in body["groups"] if g["name"] == "Peças desenhadas")
    assert {v["key"] for v in group["values"]} >= {"pd.indice", "pd.n_paginas_pdf", "pd.folhas"}
    assert body["drawings_check"]["missing_in_pdf"] == ["EL003"]


def test_pages_that_disagree_open_a_conflict(api: Api) -> None:
    pages = [
        factories.title_block("EL001", "PLANTA 1"),
        factories.title_block("EL002", "PLANTA 2", fase="PROJETO BASE"),
    ]
    fase = values(ficha_after(api, ("EL.pdf", factories.drawings_pdf(pages))))[
        "pd.carimbadura.fase"
    ]
    assert fase["status"] == "conflict" and len(fase["conflict"]["candidates"]) == 2


def test_camara_municipal_and_municipio_are_the_same_requerente(api: Api) -> None:
    lpu = factories.bom(factories.LPU_ROWS, "LPU")  # Adjudicante: Município de Teste
    pdf = factories.drawings_set(CODES, requerente="CÂMARA MUNICIPAL DE TESTE")
    requerente = values(ficha_after(api, ("LPU.xlsx", lpu), ("EL.pdf", pdf)))["id.requerente.nome"]
    assert requerente["status"] == "pending"
