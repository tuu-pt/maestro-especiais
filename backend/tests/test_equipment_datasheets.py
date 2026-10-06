"""Datasheets, parameters and the curator's review of the equipment library (Phase 7, task 2)."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from pdfs import datasheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.equipment.seed import seed_equipment
from app.ingest.datasheet import issue_date, language, read_datasheet
from app.library.seed import seed_blocks
from app.library.sources import seed_sources
from app.models import AuditEvent, Equipment, Requirement, TemplateBlock
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"

L14 = datasheet(
    "Tromilux 2525 - aplique LED de encastrar", "Grau de proteção IP65 IK08", "1,5 W 4000 K 90 lm",
    more=["Ficha técnica · Rev. 03/2021"],
)  # fmt: skip


# ---------------------------------------------------------------- the reader


def test_a_datasheet_is_read_by_patterns_page_by_page() -> None:
    reading = read_datasheet(L14)

    found = {(f.reading.name, f.reading.value, f.page) for f in reading.params}
    assert found == {("ip_rating", "IP65", 1), ("ik_rating", "IK08", 1), ("power_w", 1.5, 1),
                     ("color_temperature_k", 4000.0, 1), ("luminous_flux_lm", 90.0, 1)}  # fmt: skip
    assert (reading.pages, reading.issue_date) == (2, date(2021, 3, 1))
    assert reading.warnings == []


@pytest.mark.parametrize(
    ("text", "when"),
    [("Rev. 03/2021", date(2021, 3, 1)), ("Data: 15/06/2022", date(2022, 6, 15)),
     ("Edição: março de 2020", date(2020, 3, 1)), ("Issued 2023-11", date(2023, 11, 1)),
     ("Fecha: enero 2019", date(2019, 1, 1)), ("Modelo 03/2021 IP65", None)],
)  # fmt: skip
def test_the_issue_date_is_read_only_next_to_a_dating_word(text: str, when: date | None) -> None:
    assert issue_date(text)[0] == when


def test_the_language_and_what_a_datasheet_does_not_say() -> None:
    assert language("Power supply and dimensions of the housing for the outdoor use") == "en"
    reading = read_datasheet(datasheet("Catálogo geral"))
    assert reading.params == [] and len(reading.warnings) == 2  # no parameter, no date


# ---------------------------------------------------------------- the library API


@pytest.fixture
def library(db: Session, store: ObjectStore) -> dict[str, Any]:
    if not (FIXTURES / "R1").is_dir() or not (FIXTURES / "R2").is_dir():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))
    seed_equipment(db)
    db.commit()
    l14 = db.scalars(select(Equipment).where(Equipment.code == "L14")).one()
    return {"l14": str(l14.id)}


def upload(api: Api, equipment_id: str, data: bytes, login: str = "curador") -> Any:
    return api.as_(login).post(
        f"/api/equipment/{equipment_id}/datasheets",
        files={"file": ("L14 Tromilux.pdf", data, "application/pdf")},
    )


def test_everyone_reads_the_library(api: Api, library: dict[str, Any]) -> None:
    items = api.as_("redator").get("/api/equipment").json()
    detail = api.as_("tecnico").get(f"/api/equipment/{library['l14']}").json()

    assert len(items) > 60 and {i["status"] for i in items} == {"proposed"}
    assert detail["code"] == "L14" and detail["verdict"] == "no_datasheet"
    assert {p["origin"] for p in detail["params"]} == {"cte"}
    assert {c["param"] for c in detail["checks"]} >= {"ip_rating", "ik_rating", "power_w"}
    assert all(c["result"] == "no_datasheet" for c in detail["checks"])
    lights = api.as_("tecnico").get("/api/equipment", params={"category": "luminaria"}).json()
    assert {i["category"] for i in lights} == {"luminaria"}


def test_only_a_curator_adds_a_datasheet(api: Api, library: dict[str, Any]) -> None:
    assert upload(api, library["l14"], L14, login="tecnico").status_code == 403
    assert upload(api, library["l14"], b"not a pdf").status_code == 422

    added = upload(api, library["l14"], L14)
    again = upload(api, library["l14"], L14)

    assert added.status_code == 201, added.text and again.status_code == 200
    body = added.json()
    assert body["datasheet"]["issue_date"] == "2021-03-01" and body["params_to_review"] == 5
    checks = {c["param"]: c for c in body["checks"]}
    assert checks["ip_rating"]["result"] == "unconfirmed_ok"  # IP65 >= IP65, not reviewed yet
    assert checks["ik_rating"]["result"] == "unconfirmed_fails"  # IK08 < IK10
    assert checks["ik_rating"]["offered"] == "IK08" and checks["ik_rating"]["page"] == 1
    assert body["verdict"] == "to_confirm"
    file = api.as_("redator").get(f"/api/equipment/datasheets/{body['datasheet']['id']}/file")
    assert file.status_code == 200 and file.content == L14


def test_a_reviewed_parameter_decides_and_a_new_datasheet_replaces_the_old(
    api: Api, library: dict[str, Any], db: Session
) -> None:
    body = upload(api, library["l14"], L14).json()
    ik = next(p for p in body["params"] if p["name"] == "ik_rating" and p["origin"] == "datasheet")

    reviewed = api.as_("curador").patch(f"/api/equipment/params/{ik['id']}", json={}).json()
    assert reviewed["verdict"] == "fails"
    corrected = api.as_("curador").patch(f"/api/equipment/params/{ik['id']}",
                                         json={"value": "IK10", "page": 2}).json()  # fmt: skip
    assert {c["param"]: c["result"] for c in corrected["checks"]}["ik_rating"] == "ok"
    bad = api.as_("curador").patch(f"/api/equipment/params/{ik['id']}", json={"value": "dez"})
    assert bad.status_code == 422

    newer = upload(api, library["l14"], datasheet("IP66 IK10 1,5 W 4000 K", "Rev. 01/2025"))
    sheets = newer.json()["datasheets"]
    assert [s["status"] for s in sheets] == ["current", "outdated"]
    assert newer.json()["datasheet"]["issue_date"] == "2025-01-01"
    actions = [e.action for e in db.scalars(select(AuditEvent).where(
        AuditEvent.entity_type == "equipment"))]  # fmt: skip
    assert actions.count("equipment.datasheet_added") == 2
    assert "equipment.param_reviewed" in actions


def test_the_curator_writes_what_the_patterns_did_not_read(
    api: Api, library: dict[str, Any]
) -> None:
    client = api.as_("curador")
    assert client.post(f"/api/equipment/{library['l14']}/params",
                       json={"name": "ik_rating", "value": "10"}).status_code == 409  # fmt: skip
    sheet = upload(api, library["l14"], datasheet("Catálogo")).json()["datasheet"]
    client.patch(f"/api/equipment/datasheets/{sheet['id']}", json={"issue_date": "2024-05"})

    added = client.post(f"/api/equipment/{library['l14']}/params",
                        json={"name": "ik_rating", "value": "10", "page": 1})  # fmt: skip

    assert added.status_code == 201
    param = next(p for p in added.json()["params"] if p["origin"] == "datasheet")
    assert (param["value"], param["review_status"]) == ("IK10", "reviewed")
    assert added.json()["datasheet"]["issue_date"] == "2024-05-01"


def test_review_and_edit_an_item(api: Api, library: dict[str, Any]) -> None:
    client = api.as_("curador")
    approved = client.post(f"/api/equipment/{library['l14']}/review",
                           json={"decision": "approved"}).json()  # fmt: skip
    assert approved["status"] == "approved"

    edited = client.patch(
        f"/api/equipment/{library['l14']}",
        json={"model": "2525 LED", "note": "Modelo atual do fabricante."},
    )

    assert edited.json()["status"] == "proposed" and edited.json()["model"] == "2525 LED"
    assert client.patch(f"/api/equipment/{library['l14']}",
                        json={"category": "nada", "note": "teste"}).status_code == 422  # fmt: skip


def test_requirements_are_reviewed_and_approved_with_their_block(
    api: Api, library: dict[str, Any], db: Session
) -> None:
    supply = "ele.cte.condicoes_tecnicas_especiais.entrada_de_energia"
    needs = api.as_("tecnico").get("/api/equipment/requirements",
                                   params={"block_key": supply}).json()  # fmt: skip
    icc = next(r for r in needs if r["param_name"] == "icc_ka")
    corrected = api.as_("curador").patch(
        f"/api/equipment/requirements/{icc['id']}",
        json={"value": "20", "note": "Icc do distribuidor."},
    )
    assert corrected.json()["value"] == 20.0 and corrected.json()["status"] == "proposed"

    block = db.scalars(select(TemplateBlock).where(TemplateBlock.key == supply)).one()
    api.as_("curador").post(f"/api/library/blocks/{block.id}/review",
                            json={"decision": "approved"})  # fmt: skip

    db.expire_all()
    statuses = {r.status for r in db.scalars(select(Requirement).where(
        Requirement.block_key == supply))}  # fmt: skip
    assert statuses == {"approved"}
