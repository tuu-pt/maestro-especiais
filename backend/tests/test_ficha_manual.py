"""Manual values in the ficha-base (Phase 6, task 1a): what no source of the project gives."""

from typing import Any

import pytest
from conftest import Api
from reference_projects import have_fixtures, load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.storage import ObjectStore

pytestmark = [
    pytest.mark.skipif(not have_fixtures(), reason="sem fixtures de R1"),
    pytest.mark.usefixtures("inline_ingestion"),
]
OBRA = "Moradia unifamiliar em Coimbra"


def add(api: Api, project_id: str, key: str, value: Any, login: str = "tecnico") -> Any:
    body = {"key": key, "value": value, "note": "Da memória do cliente."}
    return api.as_(login).post(f"/api/projects/{project_id}/ficha/values", json=body)


def test_a_missing_value_goes_into_a_new_revision_to_confirm(
    api: Api, db: Session, store: ObjectStore
) -> None:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    before = api.as_("redator").get(f"/api/projects/{project_id}/ficha").json()
    assert {"id.obra.designacao", "id.local.cp"} <= {k["key"] for k in before["missing_keys"]}

    response = add(api, project_id, "id.obra.designacao", OBRA)

    assert response.status_code == 201, response.text
    assert response.json()["source_type"] == "manual"
    ficha = api.as_("redator").get(f"/api/projects/{project_id}/ficha").json()
    assert ficha["revision"]["label"] == "B" and ficha["revision"]["status"] == "draft"
    confirmed = api.as_("tecnico").post(f"/api/ficha/revisions/{ficha['revision']['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text

    mdj = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
    cover = next(s for s in mdj.json()["sections"] if s["block_key"].endswith("capa"))
    assert "id.obra.designacao" not in cover["missing_keys"]
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "ficha.manual_value")).all()
    assert [e.payload["key"] for e in events] == ["id.obra.designacao"]
    assert OBRA not in str(events[0].payload)


def test_a_value_read_from_a_source_is_not_overwritten(api: Api) -> None:
    project_id = load_confirmed(api, "R1")
    response = add(api, project_id, "ele.potencia_alimentar_kva", 40)
    assert response.status_code == 409 and "fonte" in response.json()["detail"]


def test_numbers_and_unknown_keys(api: Api) -> None:
    project_id = load_confirmed(api, "R1")
    assert add(api, project_id, "ele.chave_inexistente", "x").status_code == 422
    assert add(api, project_id, "ele.quadros", "Q.E.G.").status_code == 422  # from the Tabela
    assert add(api, project_id, "ele.tensao_resp_kv", "não é número").status_code == 422
    ok = add(api, project_id, "ele.tensao_resp_kv", "0,4")
    assert ok.status_code == 201 and ok.json()["value"] == 0.4


@pytest.mark.parametrize("login", ["redator", "curador", "admin"])
def test_only_the_tecnico_adds_values(api: Api, login: str) -> None:
    project_id = load_confirmed(api, "R1")
    assert add(api, project_id, "id.obra.designacao", OBRA, login).status_code == 403
