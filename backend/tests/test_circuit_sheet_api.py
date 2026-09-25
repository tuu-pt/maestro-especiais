"""Linking 09-Folhas by hand and resolving circuit conflicts (roles, audit, confirmation)."""

from typing import Any

import factories
import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent

pytestmark = pytest.mark.usefixtures("inline_ingestion")


def new_project(api: Api) -> str:
    response = api.as_("redator").post("/api/projects", json={"code": "R9", "name": "Moradia"})
    return str(response.json()["id"])


def upload(api: Api, project_id: str, data: bytes, name: str) -> None:
    response = api.as_("redator").post(
        f"/api/projects/{project_id}/files", files={"file": (name, data)}
    )
    assert response.status_code == 202, response.text


def ficha(api: Api, project_id: str) -> dict[str, Any]:
    body: dict[str, Any] = api.as_("redator").get(f"/api/projects/{project_id}/ficha").json()
    return body


def circuit(body: dict[str, Any], destination: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in body["circuits"] if c["destination"] == destination)
    return found


def with_unlinked_sheet(api: Api, **cells: Any) -> tuple[str, dict[str, Any]]:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    upload(api, project_id, factories.folha09(**cells), "09-Folha de Cálculo sem nome.xls")
    body = ficha(api, project_id)
    assert body["circuit_sheets"][0]["link_status"] == "unlinked"
    return project_id, body


def link(api: Api, login: str, sheet_id: str, circuit_ids: list[str]) -> Any:
    return api.as_(login).post(
        f"/api/circuit-sheets/{sheet_id}/link", json={"circuit_ids": circuit_ids}
    )


def test_ficha_lists_sheets_and_circuit_conflicts(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    upload(api, project_id, factories.folha09(proteccao_E9=32), "09-Folha de Cálculo QEG-QP1.xls")

    body = ficha(api, project_id)
    sheet = body["circuit_sheets"][0]
    assert sheet["link_status"] == "rule" and sheet["source_file"].startswith("09-Folha")
    assert sheet["values"]["in_a"] == {"value": 32, "ref": "proteccao!E9"}
    qp1 = circuit(body, "Q.P.1")
    assert sheet["circuit_ids"] == [qp1["id"]]
    [conflict] = qp1["conflicts"]
    assert conflict["field"] == "in_a" and conflict["label"] == "In"
    assert [c["value"] for c in conflict["candidates"]] == [25, 32]
    assert body["open_conflicts"] == 1 and body["can_confirm"] is False


def test_a_person_links_a_sheet_and_the_comparison_runs(api: Api, db: Session) -> None:
    project_id, body = with_unlinked_sheet(api, proteccao_E9=32)
    sheet_id, qp1 = body["circuit_sheets"][0]["id"], circuit(body, "Q.P.1")

    response = link(api, "redator", sheet_id, [qp1["id"]])

    assert response.status_code == 200, response.text
    assert response.json()["link_status"] == "manual"
    assert [c["field"] for c in circuit(ficha(api, project_id), "Q.P.1")["conflicts"]] == ["in_a"]
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "circuit_sheet.linked")).one()
    assert event.actor_id == "dev:redator"
    assert event.payload["circuits"] == 1 and event.payload["conflicts"] == 1


def test_linking_elsewhere_drops_the_conflicts_the_sheet_had_opened(api: Api) -> None:
    project_id, body = with_unlinked_sheet(api, proteccao_E9=32)
    sheet_id = body["circuit_sheets"][0]["id"]
    link(api, "redator", sheet_id, [circuit(body, "Q.P.1")["id"]])

    link(api, "redator", sheet_id, [])

    after = ficha(api, project_id)
    assert circuit(after, "Q.P.1")["conflicts"] == []
    assert after["circuit_sheets"][0]["link_status"] == "unlinked"


def test_linking_needs_a_writer_and_a_circuit_of_the_revision(api: Api) -> None:
    _, body = with_unlinked_sheet(api)
    sheet_id = body["circuit_sheets"][0]["id"]

    assert link(api, "curador", sheet_id, []).status_code == 403
    other = "00000000-0000-0000-0000-000000000000"
    assert link(api, "tecnico", sheet_id, [other]).status_code == 422


def resolve(api: Api, login: str, conflict_id: str, **choice: Any) -> Any:
    body = {"note": "Confirmado na 09-Folha.", **choice}
    return api.as_(login).post(f"/api/ficha/conflicts/{conflict_id}/resolve", json=body)


def test_only_a_tecnico_resolves_a_circuit_conflict_and_it_is_written(
    api: Api, db: Session
) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    upload(api, project_id, factories.folha09(proteccao_E9=32), "09-Folha de Cálculo QEG-QP1.xls")
    conflict = circuit(ficha(api, project_id), "Q.P.1")["conflicts"][0]

    assert resolve(api, "redator", conflict["id"], candidate=1).status_code == 403
    response = resolve(api, "tecnico", conflict["id"], candidate=1)

    assert response.status_code == 200, response.text
    assert response.json()["in_a"] == "32.00" and response.json()["conflicts"] == []
    after = ficha(api, project_id)
    assert after["open_conflicts"] == 0 and after["can_confirm"] is True
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "ficha.circuit_conflict_resolved")
    ).one()
    assert event.payload == {
        "field": "in_a",
        "circuit": "Q.E.G. → Q.P.1",
        "choice": "candidate",
        "source_type": "calc_sheet",
        "project_id": project_id,
    }


def test_a_manual_value_must_be_a_number(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    upload(api, project_id, factories.folha09(proteccao_E9=32), "09-Folha de Cálculo QEG-QP1.xls")
    conflict = circuit(ficha(api, project_id), "Q.P.1")["conflicts"][0]

    assert resolve(api, "tecnico", conflict["id"], manual_value="trinta").status_code == 422
    response = resolve(api, "tecnico", conflict["id"], manual_value="28")
    assert response.status_code == 200 and response.json()["in_a"] == "28.00"


def test_confirming_is_refused_while_a_circuit_conflict_is_open(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(R29=34.5), "FE.xlsm")
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    upload(api, project_id, factories.folha09(proteccao_E9=32), "09-Folha de Cálculo QEG-QP1.xls")
    revision_id = ficha(api, project_id)["revision"]["id"]

    response = api.as_("tecnico").post(f"/api/ficha/revisions/{revision_id}/confirm")
    assert response.status_code == 409
