"""The equipment of a project: one slot per reference line of its CTE (Phase 7, task 3)."""

import io
import zipfile
from typing import Any

import pytest
from conftest import Api
from reference_projects import load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.library.docx_blocks import DOCUMENT
from app.models import AuditEvent, Document, Equipment, ProjectEquipment
from app.storage import ObjectStore

pytestmark = pytest.mark.usefixtures("inline_ingestion")


@pytest.fixture
def cte(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    db.commit()
    project_id = load_confirmed(api, "R1")
    response = api.as_("redator").post(f"/api/projects/{project_id}/documents",
                                       json={"type": "CTE"})  # fmt: skip
    assert response.status_code == 201, response.text
    return {"project": project_id, "document": response.json()["id"]}


def slots(api: Api, project_id: str) -> list[dict[str, Any]]:
    body = api.as_("redator").get(f"/api/projects/{project_id}/equipment").json()
    return list(body["slots"])


def slot(items: list[dict[str, Any]], **where: Any) -> dict[str, Any]:
    return next(s for s in items if all(s["item"][k] == v for k, v in where.items()))


def drawings(data: bytes) -> int:
    return zipfile.ZipFile(io.BytesIO(data)).read(DOCUMENT).decode().count("<w:drawing")


def test_the_cte_of_r1_has_the_equipment_of_r1(api: Api, cte: dict[str, Any]) -> None:
    items = slots(api, cte["project"])

    portinhola = slot(items, reference="+32470")
    assert portinhola["section_title"] == "Entrada de Energia"
    assert portinhola["is_reference"] and not portinhola["chosen"]
    assert portinhola["ficha_key"] == "eq.portinhola" and portinhola["or_equivalent"]
    assert portinhola["verdict"] == "no_datasheet"
    assert {c["param"] for c in portinhola["checks"]} == {"ip_rating", "ik_rating", "icc_ka"}
    l14 = slot(items, code="L14")
    assert (l14["quantity"], l14["unit"]) == ("21.000", "un")  # the MQT article "L14"
    assert {s["item"]["manufacturer"] for s in items} >= {"Quitérios", "EFAPEL", "Tromilux"}
    assert not any(s["item"]["manufacturer"] == "Trina" for s in items)  # R2 only (no FV in R1)


def test_an_alternative_needs_a_reason_and_the_same_category(
    api: Api, cte: dict[str, Any], db: Session
) -> None:
    items = slots(api, cte["project"])
    l14, l15 = slot(items, code="L14"), slot(items, code="L15")
    client = api.as_("redator")
    detail = client.get(f"/api/project-equipment/{l14['id']}").json()
    assert l15["item"]["id"] in {a["item"]["id"] for a in detail["alternatives"]}

    no_reason = client.put(f"/api/project-equipment/{l14['id']}",
                           json={"equipment_id": l15["item"]["id"]})  # fmt: skip
    other = client.put(f"/api/project-equipment/{l14['id']}",
                       json={"equipment_id": slot(items, reference="+32470")["item"]["id"],
                             "reason": "Outro equipamento do projeto."})  # fmt: skip
    chosen = client.put(
        f"/api/project-equipment/{l14['id']}",
        json={
            "equipment_id": l15["item"]["id"],
            "reason": "Mesmo aplique, com 5 W, pedido pelo dono de obra.",
        },
    )

    assert no_reason.status_code == 422 and other.status_code == 422
    assert chosen.status_code == 200, chosen.text
    body = chosen.json()
    assert body["item"]["code"] == "L15" and not body["is_reference"] and body["chosen"]
    assert {c["param"] for c in body["checks"]} >= {"power_w"}  # the line of L14 still asks
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "equipment.chosen")).one()
    assert event.payload["project_id"] == cte["project"] and event.payload["reference"] is False
    assert (
        api.as_("curador")
        .put(f"/api/project-equipment/{l14['id']}", json={"equipment_id": l15["item"]["id"]})
        .status_code
        == 403
    )


def test_a_chosen_item_brings_its_illustration_into_the_cte(
    api: Api, cte: dict[str, Any], db: Session
) -> None:
    mirror = db.scalars(select(Equipment).where(Equipment.reference == "43910 T BR")).one()
    assert mirror.image is not None  # an image of R1 only: not assembled until it is chosen
    pe = db.scalars(select(ProjectEquipment).where(
        ProjectEquipment.equipment_id == mirror.id)).one()  # fmt: skip
    before = api.as_("redator").get(f"/api/documents/{cte['document']}/draft.docx")

    confirmed = api.as_("tecnico").put(f"/api/project-equipment/{pe.id}",
                                       json={"equipment_id": str(mirror.id)})  # fmt: skip
    after = api.as_("redator").get(f"/api/documents/{cte['document']}/draft.docx")

    assert confirmed.status_code == 200 and confirmed.json()["is_reference"]
    assert drawings(after.content) == drawings(before.content) + 1


def test_an_approved_cte_keeps_its_equipment(api: Api, cte: dict[str, Any], db: Session) -> None:
    item = slots(api, cte["project"])[0]
    document = db.get(Document, cte["document"])
    assert document is not None
    document.status = "approved"
    db.commit()

    refused = api.as_("redator").put(f"/api/project-equipment/{item['id']}",
                                     json={"equipment_id": item["item"]["id"]})  # fmt: skip

    assert refused.status_code == 409


def test_a_project_without_a_cte_has_no_equipment_yet(api: Api, db: Session,
                                                       store: ObjectStore) -> None:  # fmt: skip
    project = api.as_("redator").post("/api/projects", json={"code": "SEM-CTE", "name": "X"})
    body = api.as_("redator").get(f"/api/projects/{project.json()['id']}/equipment").json()
    assert body == {"document_id": None, "document_status": None, "slots": []}
