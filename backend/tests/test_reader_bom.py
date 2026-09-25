"""MQT / LPU: both header variants, hierarchy, notes and totals, identification → ficha-base."""

from decimal import Decimal
from typing import Any

import factories
import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import bom
from app.ingest.consolidate import comparable
from app.ingest.detect import detect
from app.ingest.pipeline import ReaderError
from app.models import BomItem

MQT = factories.bom(factories.MQT_ROWS)
LPU = factories.bom(factories.LPU_ROWS, "LPU")


def test_the_title_tells_mqt_from_lpu() -> None:
    assert detect("a.xlsx", MQT).kind == "mqt"  # has "PREÇO" in the header, still an MQT
    assert detect("b.xlsx", LPU).kind == "lpu"  # has no "PREÇO" in the header, still an LPU
    assert bom.read(MQT).variant == "mqt" and bom.read(LPU).variant == "lpu"


def test_mqt_lines_keep_their_hierarchy_and_kind() -> None:
    reading = bom.read(MQT)
    by_code = {line.code: line for line in reading.lines if line.code}

    assert reading.warnings == []
    assert by_code["8"].kind == "chapter" and by_code["8"].chapter_total == Decimal("4300")
    assert by_code["8.2"].kind == "subchapter"
    assert by_code["8.2.1"].kind == "description" and by_code["8.2.1"].level == 3
    board = by_code["8.2.1.1"]
    assert (board.kind, board.level, board.parent_code) == ("article", 4, "8.2.1")
    assert (board.unit, board.quantity, board.unit_price, board.total) == (
        "un", Decimal("1"), Decimal("1100"), Decimal("1100"),
    )  # fmt: skip
    assert board.source_ref == "MQT!linha 12"
    kinds = [line.kind for line in reading.lines if not line.code]
    assert kinds == ["note", "note", "total"]  # NOTAS INICIAIS, Nota 1., TOTAL:


def test_lpu_second_header_line_names_the_columns() -> None:
    reading = bom.read(LPU)
    board = next(line for line in reading.lines if line.code == "1.8.1.1")
    assert (board.quantity, board.unit_price, board.total) == (
        Decimal("1"), Decimal("6470"), Decimal("6470"),
    )  # fmt: skip
    chapter = next(line for line in reading.lines if line.code == "1")
    assert chapter.chapter_total == Decimal("7450")


def test_identification_and_boards_go_to_the_ficha() -> None:
    values = {c.key: (c.value, c.source_ref) for c in bom.read(LPU).result.values}
    assert values["id.obra.designacao"] == ("Reabilitação do Edifício de Teste", "LPU!C2")
    assert values["id.requerente.nome"] == ("Município de Teste", "LPU!C4")
    assert values["ele.quadros"][0] == ["Q.E.G.", "Q.P.1"]  # "(piso 1)" is not in the name
    assert "id.requerente.nome" not in {c.key for c in bom.read(MQT).result.values}


def test_unknown_header_stops_reading() -> None:
    rows = [["LISTA DE PREÇOS UNITÁRIOS"], ["Ref.", "Descrição", "Valor"]]
    with pytest.raises(ReaderError, match="Cabeçalho do MQT/LPU não reconhecido"):
        bom.read(factories.bom(rows))


def test_boards_compare_by_name_and_public_bodies_by_one_name() -> None:
    tabela = ["Q.E.G.", "Q.P.1.1", "Q.P.1.2"]
    assert comparable("ele.quadros", ["Q.P.1.2", "Q.E.G", "QP1.1"]) == comparable(
        "ele.quadros", tabela
    )
    assert comparable("ele.quadros", ["Q.E.G"]) != comparable("ele.quadros", tabela)
    assert comparable("id.requerente.nome", "Câmara Municipal de Teste") == comparable(
        "id.requerente.nome", "Município de Teste"
    )
    assert comparable("id.requerente.nome", "Junta de Freguesia de Teste") != comparable(
        "id.requerente.nome", "Município de Teste"
    )


# ---------------------------------------------------------------- through the API

pytestmark = pytest.mark.usefixtures("inline_ingestion")


def new_project(api: Api) -> str:
    response = api.as_("redator").post("/api/projects", json={"code": "R9", "name": "Obra"})
    return str(response.json()["id"])


def upload(api: Api, project_id: str, data: bytes, name: str) -> dict[str, Any]:
    client = api.as_("redator")
    assert (
        client.post(f"/api/projects/{project_id}/files", files={"file": (name, data)}).status_code
        == 202
    )
    found: dict[str, Any] = next(
        f for f in client.get(f"/api/projects/{project_id}/files").json() if f["filename"] == name
    )
    return found


def values(api: Api, project_id: str) -> dict[str, dict[str, Any]]:
    body = api.as_("redator").get(f"/api/projects/{project_id}/ficha").json()
    return {v["key"]: v for g in body["groups"] for v in g["values"]}


def test_lines_are_stored_and_a_new_file_replaces_them(api: Api, db: Session) -> None:
    project_id = new_project(api)
    file = upload(api, project_id, MQT, "Mapa.xlsx")
    assert file["ingest_status"] == "done" and file["ingest_message"].startswith("MQT: 4 artigos")
    assert db.scalars(select(BomItem)).all()[0].link_status == "unlinked"

    upload(api, project_id, factories.bom(factories.MQT_ROWS[:9]), "Mapa v2.xlsx")
    assert {i.source_ref for i in db.scalars(select(BomItem))} == {
        f"MQT!linha {r}" for r in range(5, 10)
    }


def test_c7_requerente_of_the_ficha_differs_from_the_adjudicante(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(C5="Outra Entidade, Lda"), "FE.xlsm")
    upload(api, project_id, LPU, "LPU.xlsx")

    requerente = values(api, project_id)["id.requerente.nome"]
    assert requerente["status"] == "conflict" and requerente["value"] is None
    sources = [c["source_type"] for c in requerente["conflict"]["candidates"]]
    assert sources == ["ficha_eletrotecnica", "mqt"]
    assert all(c["value"] == "•••" for c in requerente["conflict"]["candidates"])  # personal


def test_the_same_boards_as_the_tabela_are_no_conflict(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")  # Q.E.G., Q.P.1
    upload(api, project_id, MQT, "Mapa.xlsx")  # Q.E.G, Q.P.1

    assert values(api, project_id)["ele.quadros"]["status"] == "pending"
