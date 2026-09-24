import logging
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


def upload(api: Api, project_id: str, data: bytes, name: str) -> dict[str, Any]:
    response = api.as_("redator").post(
        f"/api/projects/{project_id}/files", files={"file": (name, data)}
    )
    assert response.status_code in (200, 201, 202), response.text
    body: dict[str, Any] = response.json()
    return body


def ficha(api: Api, project_id: str, login: str = "redator") -> dict[str, Any]:
    body: dict[str, Any] = api.as_(login).get(f"/api/projects/{project_id}/ficha").json()
    return body


def values(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {v["key"]: v for g in body["groups"] for v in g["values"]}


def tabela_with_supply(kva: float) -> bytes:
    rows = [list(r) for r in factories.CALC_ROWS]
    rows[1][2] = kva
    return factories.tabela_calculo(rows=rows)


def with_conflict(api: Api) -> tuple[str, dict[str, Any]]:
    """Ficha 180 kVA, Tabela 200 kVA (as in case C6)."""
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(R29=180), "FE.xlsm")
    upload(api, project_id, tabela_with_supply(200), "Tabela.xlsx")
    return project_id, values(ficha(api, project_id))["ele.potencia_alimentar_kva"]


# ---------------------------------------------------------------- empty and first reading


def test_project_without_files_has_no_ficha(api: Api) -> None:
    body = ficha(api, new_project(api))

    assert body["revision"] is None and body["circuits"] == []
    assert all(g["values"] == [] for g in body["groups"])
    assert body["can_confirm"] is False


def test_ficha_is_created_from_the_ficha_eletrotecnica_with_origins(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(), "FE.xlsm")

    body = ficha(api, project_id)
    found = values(body)
    assert body["revision"]["label"] == "A" and body["revision"]["status"] == "draft"
    assert found["ele.potencia_alimentar_kva"]["value"] == 34.5
    assert found["ele.potencia_alimentar_kva"]["source_ref"] == "Ficha Eletrotecnica!R29"
    assert found["ele.potencia_alimentar_kva"]["source_file"] == "FE.xlsm"
    assert found["ele.potencia_alimentar_kva"]["status"] == "pending"


def test_personal_values_are_masked_for_every_role(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(), "FE.xlsm")

    for login in ("redator", "tecnico", "curador", "admin"):
        nome = values(ficha(api, project_id, login))["id.requerente.nome"]
        assert nome["value"] == "•••" and nome["masked"] is True
    assert (
        "Requerente Sintético" not in api.as_("admin").get(f"/api/projects/{project_id}/ficha").text
    )


def test_revealing_a_personal_value_is_audited_without_the_value(api: Api, db: Session) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(), "FE.xlsm")
    nome = values(ficha(api, project_id))["id.requerente.nome"]

    revealed = api.as_("curador").post(f"/api/ficha/values/{nome['id']}/reveal").json()

    assert revealed["value"] == "Requerente Sintético" and revealed["masked"] is False
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "ficha.value_revealed")).one()
    assert event.actor_id == "dev:curador"
    assert event.payload == {"key": "id.requerente.nome", "project_id": project_id}


def test_circuits_come_with_cal01_marks(api: Api) -> None:
    project_id = new_project(api)
    rows = [list(r) for r in factories.CALC_ROWS]
    rows[1][9], rows[1][10] = 504, 503.4  # I2 > 1,45·Iz, as in case C10
    upload(api, project_id, factories.tabela_calculo(rows=rows), "Tabela.xlsx")

    body = ficha(api, project_id)
    entry, qp1 = body["circuits"][0], body["circuits"][1]
    assert entry["source_ref"] == "Tabela!linha 3"
    assert entry["cal01"] == {"ib_in_iz": "ok", "i2_iz145": "fail"}
    assert qp1["cal01"] == {"ib_in_iz": "ok", "i2_iz145": "ok"}
    assert "MDJ" in body["cal01_note"]


# ---------------------------------------------------------------- agreement and conflicts


def test_same_power_in_both_sources_is_not_a_conflict(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(R29=34.5), "FE.xlsm")
    upload(api, project_id, tabela_with_supply(34.5), "Tabela.xlsx")

    body = ficha(api, project_id)
    assert body["open_conflicts"] == 0
    assert values(body)["ele.potencia_alimentar_kva"]["value"] == 34.5


def test_different_power_opens_a_conflict_and_nothing_is_chosen(api: Api) -> None:
    _, power = with_conflict(api)

    assert power["status"] == "conflict"
    assert power["value"] is None  # the agent does not pick one
    candidates = power["conflict"]["candidates"]
    assert [(c["value"], c["source_type"]) for c in candidates] == [
        (180, "ficha_eletrotecnica"),
        (200, "calc"),
    ]
    assert candidates[1]["source_ref"] == "Tabela!linha 3"


def test_a_newer_file_of_the_same_source_replaces_its_value(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(R29=30), "FE v0.xlsm")
    upload(api, project_id, factories.ficha_eletrotecnica(R29=34.5), "FE v1.xlsm")

    power = values(ficha(api, project_id))["ele.potencia_alimentar_kva"]
    assert power["value"] == 34.5 and power["source_file"] == "FE v1.xlsm"
    assert power["conflict"] is None


@pytest.mark.parametrize("login", ["redator", "curador", "admin"])
def test_only_the_tecnico_resolves_conflicts(api: Api, login: str) -> None:
    _, power = with_conflict(api)
    response = api.as_(login).post(
        f"/api/ficha/conflicts/{power['conflict']['id']}/resolve",
        json={"candidate": 1, "note": "Confirmado na folha"},
    )
    assert response.status_code == 403


def test_resolving_requires_a_note_and_one_choice(api: Api) -> None:
    _, power = with_conflict(api)
    url = f"/api/ficha/conflicts/{power['conflict']['id']}/resolve"
    client = api.as_("tecnico")

    assert client.post(url, json={"candidate": 1}).status_code == 422
    assert client.post(url, json={"note": "sem escolha"}).status_code == 422
    assert (
        client.post(url, json={"candidate": 1, "manual_value": 5, "note": "as duas"}).status_code
        == 422
    )


def test_tecnico_resolves_with_a_candidate_and_it_is_audited(api: Api, db: Session) -> None:
    project_id, power = with_conflict(api)

    response = api.as_("tecnico").post(
        f"/api/ficha/conflicts/{power['conflict']['id']}/resolve",
        json={"candidate": 1, "note": "A Tabela de Cálculo está atualizada"},
    )

    assert response.status_code == 200, response.text
    resolved = values(ficha(api, project_id))["ele.potencia_alimentar_kva"]
    assert resolved["value"] == 200 and resolved["source_type"] == "calc"
    assert resolved["conflict"] is None and resolved["status"] == "pending"
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "ficha.conflict_resolved")
    ).one()
    assert event.payload == {
        "project_id": project_id,
        "key": "ele.potencia_alimentar_kva",
        "choice": "candidate",
        "source_type": "calc",
    }


def test_tecnico_can_resolve_with_a_manual_value(api: Api) -> None:
    project_id, power = with_conflict(api)
    api.as_("tecnico").post(
        f"/api/ficha/conflicts/{power['conflict']['id']}/resolve",
        json={"manual_value": 190, "note": "Valor confirmado com o projetista"},
    )
    resolved = values(ficha(api, project_id))["ele.potencia_alimentar_kva"]
    assert resolved["value"] == 190 and resolved["source_type"] == "manual"


# ---------------------------------------------------------------- confirmation and revisions


def test_confirming_with_open_conflicts_is_refused(api: Api) -> None:
    project_id, _ = with_conflict(api)
    revision_id = ficha(api, project_id)["revision"]["id"]

    response = api.as_("tecnico").post(f"/api/ficha/revisions/{revision_id}/confirm")

    assert response.status_code == 409
    assert ficha(api, project_id)["can_confirm"] is False


def test_confirmation_by_the_tecnico_after_resolving(api: Api, db: Session) -> None:
    project_id, power = with_conflict(api)
    api.as_("tecnico").post(
        f"/api/ficha/conflicts/{power['conflict']['id']}/resolve",
        json={"candidate": 1, "note": "Tabela atualizada"},
    )
    body = ficha(api, project_id)
    assert body["can_confirm"] is True
    url = f"/api/ficha/revisions/{body['revision']['id']}/confirm"

    assert api.as_("redator").post(url).status_code == 403
    response = api.as_("tecnico").post(url)

    assert response.status_code == 200
    confirmed = ficha(api, project_id)
    assert confirmed["revision"]["status"] == "confirmed"
    assert confirmed["revision"]["confirmed_by"] == "dev:tecnico"
    assert all(v["status"] == "confirmed" for v in values(confirmed).values())
    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "ficha.confirmed")).one()


def test_reading_after_confirmation_starts_a_new_revision(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(), "FE.xlsm")
    revision_a = ficha(api, project_id)["revision"]["id"]
    api.as_("tecnico").post(f"/api/ficha/revisions/{revision_a}/confirm")

    upload(api, project_id, tabela_with_supply(34.5), "Tabela.xlsx")
    body = ficha(api, project_id)

    assert [(r["label"], r["status"]) for r in body["revisions"]] == [
        ("A", "confirmed"),
        ("B", "draft"),
    ]
    assert values(body)["ele.potencia_alimentar_kva"]["value"] == 34.5  # carried over
    api.as_("tecnico").post(f"/api/ficha/revisions/{body['revision']['id']}/confirm")
    statuses = [r["status"] for r in ficha(api, project_id)["revisions"]]
    assert statuses == ["superseded", "confirmed"]


def test_no_personal_value_reaches_the_logs(api: Api, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(), "FE.xlsm")
    upload(api, project_id, factories.tabela_calculo(), "Tabela.xlsx")
    ficha(api, project_id)

    for secret in ("Requerente Sintético", "requerente@example.com", "999990013", "Rua de Teste"):
        assert secret not in caplog.text


def test_values_follow_the_order_of_spec_7_2(api: Api) -> None:
    project_id = new_project(api)
    upload(api, project_id, factories.ficha_eletrotecnica(), "FE.xlsm")

    identificacao = next(
        g for g in ficha(api, project_id)["groups"] if g["name"] == "Identificação"
    )
    assert [v["key"] for v in identificacao["values"]][:3] == [
        "id.requerente.nome",
        "id.requerente.nif",
        "id.requerente.morada",
    ]
