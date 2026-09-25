"""09-Folha de Cálculo: fixed cells, link to the Tabela by board name, conflicts per field."""

from typing import Any

import factories
import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import circuit_sheet as cs
from app.ingest.pipeline import ReaderError
from app.models import Circuit, CircuitSheet, FichaConflict

SHEET = "09-Folha de Cálculo QEG-QP1.xls"  # Q.E.G. → Q.P.1 in factories.CALC_ROWS


# ---------------------------------------------------------------- reading


def test_values_are_read_from_the_mapped_cells_with_their_origin() -> None:
    reading = cs.read(factories.folha09(), SHEET)

    assert reading.template == "TUU_09" and reading.warnings == []
    assert reading.values["in_a"] == {"value": 25, "ref": "proteccao!E9"}
    assert reading.values["iz_a"] == {"value": 32, "ref": "proteccao!Z7"}  # corrected Iz
    assert reading.values["vd_section_pct"]["value"] == pytest.approx(1.1)  # fraction → %
    assert (reading.origin_hint, reading.destination_hint) == ("QEG", "QP1")


def test_unknown_template_stops_reading() -> None:
    with pytest.raises(ReaderError, match="Modelo de 09-Folha desconhecido"):
        cs.read(factories.folha09(titles={"IB": "OUTRO MODELO"}), SHEET)
    with pytest.raises(ReaderError, match="desconhecido"):
        cs.read(factories.folha09(sheets=("IB", "condutores")), SHEET)


def test_corrupted_file_is_reported() -> None:
    with pytest.raises(ReaderError, match="ilegível ou corrompida"):
        cs.read(b"\xd0\xcf\x11\xe0 not really an xls", SHEET)


def test_empty_cells_and_nameless_files_are_warnings() -> None:
    reading = cs.read(factories.folha09(proteccao_J9=None), "09-Folha de Cálculo.xls")

    assert "i2_a" not in reading.values
    assert "Célula proteccao!J9 vazia ou sem número." in reading.warnings
    assert "O nome do ficheiro não indica o troço (origem-destino)." in reading.warnings


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        (29.9, 29.8701, True),  # the Tabela shows one decimal
        (82.7, 82.64999999999999, True),  # Excel float noise
        (1, 0.58, True),  # the Tabela shows no decimals
        (0.9, 0.7597, False),  # R1, Q.E.G. → Q.P.1.2
        (504, 400, False),
        (13.04, 12.987, False),
    ],
)
def test_numbers_are_compared_at_the_less_precise_value(a: float, b: float, same: bool) -> None:
    assert cs.same_reading(a, b) is same


# ---------------------------------------------------------------- linking and conflicts


def new_project(api: Api) -> str:
    response = api.as_("redator").post("/api/projects", json={"code": "R9", "name": "Moradia"})
    return str(response.json()["id"])


def upload(api: Api, project_id: str, data: bytes, name: str) -> dict[str, Any]:
    response = api.as_("redator").post(
        f"/api/projects/{project_id}/files", files={"file": (name, data)}
    )
    assert response.status_code == 202, response.text
    listed = api.as_("redator").get(f"/api/projects/{project_id}/files").json()
    found: dict[str, Any] = next(f for f in listed if f["filename"] == name)
    return found


def circuit_conflicts(db: Session) -> dict[str, list[Any]]:
    rows = db.scalars(select(FichaConflict).where(FichaConflict.circuit_id.is_not(None)))
    return {
        f"{c.circuit.destination if c.circuit else None}.{c.field}": [
            x["value"] for x in c.candidates
        ]
        for c in rows
    }


@pytest.mark.usefixtures("inline_ingestion")
def test_a_sheet_that_agrees_is_linked_and_opens_no_conflict(api: Api, db: Session) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    file = upload(api, project_id, factories.folha09(), SHEET)

    assert file["ingest_status"] == "done"
    assert "associada ao troço pelo nome do ficheiro" in file["ingest_message"]
    sheet = db.scalars(select(CircuitSheet)).one()
    circuit = db.get(Circuit, sheet.circuit_ids[0])
    assert circuit is not None and circuit.destination == "Q.P.1"
    assert sheet.link_status == "rule" and circuit_conflicts(db) == {}


@pytest.mark.usefixtures("inline_ingestion")
def test_a_different_value_opens_a_conflict_on_the_circuit_field(api: Api, db: Session) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    file = upload(api, project_id, factories.folha09(proteccao_E9=32), SHEET)

    assert "1 conflito para resolver" in file["ingest_message"]
    assert circuit_conflicts(db) == {"Q.P.1.in_a": [25, 32]}  # Tabela first, then the sheet
    circuit = db.scalars(select(Circuit).where(Circuit.destination == "Q.P.1")).one()
    assert circuit.in_a == 25  # nothing chosen: the Tabela value stays until a person resolves
    conflict = circuit.conflicts[0]
    assert conflict.candidates[1]["source_ref"] == "09-Folha QEG-QP1 · proteccao!E9"


@pytest.mark.usefixtures("inline_ingestion")
def test_sheets_read_before_the_tabela_are_linked_when_it_arrives(api: Api, db: Session) -> None:
    project_id = new_project(api)
    file = upload(api, project_id, factories.folha09(proteccao_E9=32), SHEET)
    assert "ainda não há Tabela de Cálculo" in file["ingest_message"]

    tabela = upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")

    assert "1 conflito com as 09-Folhas" in tabela["ingest_message"]
    assert db.scalars(select(CircuitSheet)).one().link_status == "rule"


@pytest.mark.usefixtures("inline_ingestion")
def test_a_sheet_without_a_unique_circuit_waits_for_a_person(api: Api, db: Session) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    file = upload(api, project_id, factories.folha09(), "09-Folha de Cálculo QEG-QP9.xls")

    assert "por associar: escolha o troço na ficha" in file["ingest_message"]
    sheet = db.scalars(select(CircuitSheet)).one()
    assert (sheet.link_status, sheet.circuit_ids) == ("unlinked", [])


@pytest.mark.usefixtures("inline_ingestion")
def test_a_new_tabela_keeps_the_links_made_by_a_person(api: Api, db: Session) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    upload(api, project_id, factories.folha09(), "09-Folha de Cálculo sem nome.xls")
    sheet = db.scalars(select(CircuitSheet)).one()
    qp1 = db.scalars(select(Circuit).where(Circuit.destination == "Q.P.1")).one()
    sheet.circuit_ids, sheet.link_status = [str(qp1.id)], "manual"
    db.flush()

    rows = [list(r) for r in factories.CALC_ROWS]
    rows[3][13] = 1.4  # another voltage drop in Q.E.G. → Q.P.1
    upload(api, project_id, factories.tabela_calculo(rows=rows), "Tabela v2.xlsx")

    db.refresh(sheet)
    new_qp1 = db.scalars(select(Circuit).where(Circuit.destination == "Q.P.1")).one()
    assert sheet.link_status == "manual" and sheet.circuit_ids == [str(new_qp1.id)]
    assert circuit_conflicts(db) == {"Q.P.1.vd_section_pct": [1.4, 1.1]}
