"""MQT/LPU article links: each rule, the unlinked rest, and links made by a person (audited)."""

from typing import Any

import factories
import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.bom_links import board_name, link_for
from app.models import AuditEvent, BomItem


@pytest.mark.parametrize(
    ("designation", "key", "rule"),
    [
        ("Q.E.G", "ele.quadros", "board"),
        ("Q.P.EXTERIOR (CVE)", "ele.quadros", "board"),
        ("Q.UPS 10kVA", "ele.quadros", "board"),
        ("Caixa Portinhola P100, REF 32470", "eq.portinhola", "portinhola"),
        ("Fornecimento e instalação de Carregador de veículos 7,4 kW", "sys.ve", "ev_charger"),
        ("Fornecimento e instalação de módulos fotovoltaicos 450 Wp", "sys.fv", "pv_module"),
        ("L4.1 - Luminária tipo painel de encastrar", "eq.luminarias", "luminaire:L4.1"),
        ("SNC \u2013 Luminária de Sanca (Régua linear)", "eq.luminarias", "luminaire:SNC"),
    ],
)
def test_each_rule(designation: str, key: str, rule: str) -> None:
    found = link_for(designation)
    assert found is not None and (found.key, found.rule) == (key, rule)


@pytest.mark.parametrize(
    "designation",
    [
        "Quadro elétrico de entrada, conforme esquema",  # a sentence, not a board name
        "Fornecimento e instalação de inversor",
        "XZ1(frt,zh) 5G10mm²",
        "Iluminação de segurança permanente",
        None,
    ],
)
def test_articles_no_rule_recognizes_stay_unlinked(designation: str | None) -> None:
    assert link_for(designation) is None


def test_board_names_keep_their_name_without_the_note() -> None:
    assert board_name("Q.P.1 (piso 1)") == "Q.P.1"
    assert board_name("Quadro Q.E.G.") is None


# ---------------------------------------------------------------- through the API

pytestmark = pytest.mark.usefixtures("inline_ingestion")
MQT = factories.bom(factories.MQT_ROWS)


def project_with_mqt(api: Api) -> str:
    client = api.as_("redator")
    project_id = str(client.post("/api/projects", json={"code": "R9", "name": "Obra"}).json()["id"])
    response = client.post(f"/api/projects/{project_id}/files", files={"file": ("MQT.xlsx", MQT)})
    assert response.status_code == 202
    return project_id


def items(api: Api, project_id: str) -> dict[str, dict[str, Any]]:
    body = api.as_("redator").get(f"/api/projects/{project_id}/ficha").json()
    return {i["code"]: i for i in body["bom_items"] if i["code"]}


def test_rules_link_articles_when_the_file_is_read(api: Api) -> None:
    found = items(api, project_with_mqt(api))

    assert (found["8.2.1.1"]["link_key"], found["8.2.1.1"]["link_status"]) == (
        "ele.quadros",
        "rule",
    )
    assert found["8.2.1.1"]["link_label"] == "Quadros"
    assert found["8.1.1"]["link_key"] == "eq.portinhola"
    assert found["8.3.1"]["link_key"] == "sys.ve"
    assert found["8.2"]["link_status"] == "unlinked"  # a subchapter is not linked


def link(api: Api, login: str, item_id: str, key: str | None) -> Any:
    return api.as_(login).post(f"/api/bom-items/{item_id}/link", json={"key": key})


def test_a_person_links_an_article_and_it_is_audited(api: Api, db: Session) -> None:
    project_id = project_with_mqt(api)
    item = items(api, project_id)["8.3.1"]

    response = link(api, "redator", item["id"], "sys.fv")

    assert response.status_code == 200, response.text
    assert (response.json()["link_key"], response.json()["link_status"]) == ("sys.fv", "manual")
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "bom_item.linked")).one()
    assert event.payload["code"] == "8.3.1" and event.payload["link_key"] == "sys.fv"
    assert link(api, "redator", item["id"], None).json()["link_status"] == "unlinked"


def test_linking_is_refused_for_readers_bad_keys_and_non_articles(api: Api) -> None:
    project_id = project_with_mqt(api)
    found = items(api, project_id)

    assert link(api, "curador", found["8.3.1"]["id"], "sys.ve").status_code == 403
    assert link(api, "tecnico", found["8.3.1"]["id"], "id.requerente.nome").status_code == 422
    assert link(api, "tecnico", found["8.2"]["id"], "ele.quadros").status_code == 409


def test_links_made_by_a_person_survive_a_newer_file(api: Api, db: Session) -> None:
    project_id = project_with_mqt(api)
    link(api, "redator", items(api, project_id)["8.3.1"]["id"], "sys.fv")

    client = api.as_("redator")
    client.post(f"/api/projects/{project_id}/files", files={"file": ("MQT v2.xlsx", MQT + b" ")})

    after = items(api, project_id)["8.3.1"]
    assert (after["link_key"], after["link_status"]) == ("sys.fv", "manual")
    assert len(db.scalars(select(BomItem).where(BomItem.code == "8.3.1")).all()) == 1
