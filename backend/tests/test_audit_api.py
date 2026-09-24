from typing import Any

import factories
import pytest
from conftest import Api

pytestmark = pytest.mark.usefixtures("inline_ingestion")


def setup_project(api: Api) -> str:
    project = api.as_("redator").post("/api/projects", json={"code": "R9", "name": "M"}).json()
    for name, data in (
        ("FE Fulano.xlsm", factories.ficha_eletrotecnica(R29=180)),
        ("Tabela.xlsx", factories.tabela_calculo()),
    ):
        api.as_("redator").post(
            f"/api/projects/{project['id']}/files", files={"file": (name, data)}
        )
    return str(project["id"])


def test_new_database_has_no_activity(api: Api) -> None:
    assert api.as_("redator").get("/api/activity").json() == []


def test_project_timeline_tells_who_did_what(api: Api) -> None:
    project_id = setup_project(api)

    timeline: list[dict[str, Any]] = (
        api.as_("curador").get(f"/api/projects/{project_id}/audit").json()
    )

    assert [e["action"] for e in timeline] == [
        "project.created",
        "file.uploaded",
        "file.ingested",
        "file.uploaded",
        "file.ingested",
    ]
    assert timeline[0]["description"] == "Projeto R9 criado"
    assert timeline[0]["actor_name"] == "Redator (desenvolvimento)"
    assert timeline[2]["actor_type"] == "system" and timeline[2]["actor_name"] == "Sistema"
    assert timeline[4]["description"].startswith("Leu Tabela de Cálculo: ")
    assert "conflito" in timeline[4]["description"]


def test_timeline_never_shows_personal_values_or_file_names(api: Api) -> None:
    project_id = setup_project(api)
    text = api.as_("admin").get(f"/api/projects/{project_id}/audit").text

    for secret in ("Fulano", "Requerente Sintético", "999990013"):
        assert secret not in text


def test_activity_lists_the_newest_events_with_the_project_code(api: Api) -> None:
    setup_project(api)

    events = api.as_("redator").get("/api/activity?limit=2").json()

    assert len(events) == 2
    assert events[0]["action"] == "file.ingested" and events[0]["project_code"] == "R9"
    assert events[0]["at"] >= events[1]["at"]
