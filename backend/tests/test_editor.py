"""Editor actions (screen D): unlock, activation, hand edits with COE-01, review (task 5)."""

import copy
from typing import Any

import pytest
from conftest import Api
from reference_projects import load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ValueRef
from app.storage import ObjectStore

pytestmark = pytest.mark.usefixtures("inline_ingestion")


@pytest.fixture
def mdj(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    doc = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
    return {"project_id": project_id, **doc.json()}


def section(api: Api, doc: dict[str, Any], suffix: str) -> dict[str, Any]:
    fresh = api.as_("redator").get(f"/api/documents/{doc['id']}").json()
    return next(s for s in fresh["sections"] if s["block_key"].endswith(suffix))


def audit(api: Api, doc: dict[str, Any]) -> list[str]:
    return [
        e["description"]
        for e in api.as_("redator").get(f"/api/projects/{doc['project_id']}/audit").json()
    ]


def test_a_fixed_block_needs_an_unlock_with_a_reason(api: Api, mdj: dict[str, Any]) -> None:
    fixed = section(api, mdj, "quedas_de_tensao")
    content = copy.deepcopy(fixed["content"])
    content["content"][1]["content"][0]["content"][0]["text"] = "Texto alterado."

    refused = api.as_("redator").put(
        f"/api/sections/{fixed['id']}/content", json={"content": content}
    )
    assert refused.status_code == 409 and "desbloqueie com justificação" in refused.json()["detail"]
    short = api.as_("redator").post(f"/api/sections/{fixed['id']}/unlock", json={"reason": "x"})
    assert short.status_code == 422
    api.as_("redator").post(
        f"/api/sections/{fixed['id']}/unlock", json={"reason": "Fórmula errada no modelo."}
    )
    edited = api.as_("redator").put(
        f"/api/sections/{fixed['id']}/content", json={"content": content}
    )

    assert edited.status_code == 200 and edited.json()["version"] == 2
    assert (
        section(api, mdj, "quedas_de_tensao")["unlocked"]["reason"] == "Fórmula errada no modelo."
    )
    assert "Desbloqueou o bloco fixo «Quedas de Tensão»: Fórmula errada no modelo." in audit(
        api, mdj
    )


def test_an_inactive_block_can_be_activated_with_a_reason(api: Api, mdj: dict[str, Any]) -> None:
    rpc = section(api, mdj, "regulamento_dos_produtos_de_construcao_rpc")
    assert not rpc["active"]

    response = api.as_("tecnico").post(
        f"/api/sections/{rpc['id']}/activation",
        json={"active": True, "reason": "Pedido do dono de obra."},
    )

    assert response.status_code == 200
    now = section(api, mdj, "regulamento_dos_produtos_de_construcao_rpc")
    assert now["active"] and now["activation_override"]["rule_result"] is False
    assert now["active_reason"]  # the reason of the rule stays visible
    assert any(d.startswith("Ativou «REGULAMENTO DOS PRODUTOS") for d in audit(api, mdj))


def _power_mark(content: dict[str, Any]) -> dict[str, Any]:
    for node in content["content"]:
        for child in node.get("content") or []:
            for mark in child.get("marks") or []:
                if mark["type"] == "value" and mark["attrs"]["key"] == "ele.potencia_alimentar_kva":
                    return dict(child)
    raise AssertionError("sem valor de potência")


def test_editing_a_value_asks_for_a_confirmation_and_marks_coe01(
    api: Api, mdj: dict[str, Any], db: Session
) -> None:
    supply = section(api, mdj, "alimentacao_de_energia")
    content = copy.deepcopy(supply["content"])
    _power_mark(content)  # exists
    for node in content["content"]:
        for child in node.get("content") or []:
            if any(m["type"] == "value" for m in child.get("marks") or []):
                child["text"] = "41,4"

    first = api.as_("redator").put(
        f"/api/sections/{supply['id']}/content", json={"content": content}
    )
    assert first.status_code == 409
    assert (
        first.json()["detail"]["message"]
        == "Confirme a alteração de valores que vêm da ficha-base."
    )
    confirmed = api.as_("redator").put(
        f"/api/sections/{supply['id']}/content", json={"content": content, "confirm_values": True}
    )

    assert confirmed.json() == {"version": 2, "values_changed": 1}
    [edited] = [r.edited for r in db.scalars(select(ValueRef)) if r.edited]
    assert edited is not None
    assert edited["coe_01"] is True and edited["from_key"] == "ele.potencia_alimentar_kva"
    assert "Editou «Alimentação de Energia» (valores da ficha alterados)" in audit(api, mdj)


def test_review(api: Api, mdj: dict[str, Any]) -> None:
    fixed = section(api, mdj, "quedas_de_tensao")
    pending = section(api, mdj, "ele.mdj.introducao")
    cover = section(api, mdj, "ele.mdj.capa")  # id.obra.designacao missing in R1

    ok = api.as_("tecnico").post(f"/api/sections/{fixed['id']}/review", json={})
    assert ok.json()["status"] == "reviewed"
    not_written = api.as_("tecnico").post(f"/api/sections/{pending['id']}/review", json={})
    assert not_written.status_code == 409 and "texto adaptativo" in not_written.json()["detail"]
    missing = api.as_("tecnico").post(f"/api/sections/{cover['id']}/review", json={})
    assert missing.status_code == 409 and "Falta dado" in missing.json()["detail"]
    assert "Marcou «Quedas de Tensão» como revista" in audit(api, mdj)


def test_the_document_says_what_the_editor_needs(api: Api, mdj: dict[str, Any]) -> None:
    intro = section(api, mdj, "ele.mdj.introducao")
    fixed = section(api, mdj, "quedas_de_tensao")
    assert intro["has_adaptive"] and not fixed["has_adaptive"]
    assert intro["proposals"] == 0 and intro["unlocked"] is None


@pytest.mark.parametrize("login", ["curador", "admin"])
def test_only_writers_edit(api: Api, mdj: dict[str, Any], login: str) -> None:
    fixed = section(api, mdj, "quedas_de_tensao")
    assert (
        api.as_(login)
        .post(f"/api/sections/{fixed['id']}/unlock", json={"reason": "Teste."})
        .status_code
        == 403
    )
