"""EQP-01, EQP-02 and EQP-03: the equipment of the CTE against its datasheets (Phase 7, task 4)."""

import uuid
from typing import Any

import pytest
from conftest import Api, Published, RecordingQueue
from pdfs import datasheet
from reference_projects import load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Equipment, ProjectEquipment, Requirement
from app.storage import ObjectStore
from app.validation.engine import run_validation

pytestmark = pytest.mark.usefixtures("inline_ingestion", "inline_validation")
SUPPLY = "ele.cte.condicoes_tecnicas_especiais.entrada_de_energia"


@pytest.fixture
def inline_validation(
    db: Session, store: ObjectStore, settings: Settings, published: Published,
    validation_queue: RecordingQueue,
) -> None:  # fmt: skip
    def run(run_id: uuid.UUID) -> None:
        run_validation(db, store, settings, published, run_id)

    validation_queue.run = run


@pytest.fixture
def r1(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    db.commit()
    project_id = load_confirmed(api, "R1")
    made = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "CTE"})
    assert made.status_code == 201, made.text
    portinhola = db.scalars(select(Equipment).where(Equipment.reference == "+32470")).one()
    return {"project": project_id, "portinhola": str(portinhola.id)}


def validate(api: Api, project_id: str) -> list[dict[str, Any]]:
    started = api.as_("redator").post(f"/api/projects/{project_id}/validation", json={})
    assert started.status_code == 202, started.text
    state = api.as_("redator").get(f"/api/projects/{project_id}/validation").json()
    return [i for i in state["issues"] if i["rule_id"].startswith("EQP")]


def approve_supply(db: Session) -> None:
    for r in db.scalars(select(Requirement).where(Requirement.block_key == SUPPLY)):
        r.status = "approved"
    db.commit()


def add_sheet(api: Api, equipment_id: str, data: bytes, review: bool) -> dict[str, Any]:
    body = (
        api.as_("curador")
        .post(
            f"/api/equipment/{equipment_id}/datasheets",
            files={"file": ("ficha.pdf", data, "application/pdf")},
        )
        .json()
    )
    if review:
        for p in body["params"]:
            if p["origin"] == "datasheet":
                body = api.as_("curador").patch(f"/api/equipment/params/{p['id']}", json={}).json()
    return dict(body)


def test_without_datasheets_only_eqp_03_informs(api: Api, r1: dict[str, Any]) -> None:
    issues = validate(api, r1["project"])

    assert issues and {i["rule_id"] for i in issues} == {"EQP-03"}
    assert {i["severity"] for i in issues} == {"info"}
    portinhola = next(i for i in issues if "+32470" in i["message"])
    assert "Entrada de Energia" in portinhola["message"]
    assert "open_equipment" in portinhola["actions"] and "ask_curator" in portinhola["actions"]
    # one per item, though an item may fill several slots
    assert len({i["message"] for i in issues}) == len(issues)


def test_a_reviewed_parameter_that_fails_is_critical(
    api: Api, r1: dict[str, Any], db: Session
) -> None:
    approve_supply(db)
    add_sheet(api, r1["portinhola"], datasheet("Portinhola PBT Tri", "IP44 IK10 Icc 25 kA",
                                               "Rev. 05/2025"), review=True)  # fmt: skip

    issues = validate(api, r1["project"])

    [critical] = [i for i in issues if i["rule_id"] == "EQP-01"]
    assert critical["severity"] == "critical"
    assert "IP44" in critical["message"] and "≥ IP55" in critical["message"]
    assert critical["evidence"]["offered"] == "IP44" and critical["evidence"]["page"] == 1
    assert critical["location"]["section_title"] == "Entrada de Energia"
    assert not any(i["rule_id"] == "EQP-03" and "+32470" in i["message"] for i in issues)


def test_parameters_not_reviewed_ask_to_confirm_and_what_is_not_said_informs(
    api: Api, r1: dict[str, Any], db: Session
) -> None:
    approve_supply(db)
    add_sheet(api, r1["portinhola"], datasheet("IP65 IK10", "Rev. 05/2025"), review=False)

    issues = validate(api, r1["project"])

    eqp = {i["severity"]: i for i in issues if i["rule_id"] == "EQP-01"}
    assert set(eqp) == {"warning", "info"}
    assert "confirmar na ficha técnica" in eqp["warning"]["message"]
    assert "Corrente de curto-circuito" in eqp["info"]["message"]  # 25 kA is not on the sheet


def test_proposed_requirements_are_not_checked_yet(api: Api, r1: dict[str, Any]) -> None:
    add_sheet(api, r1["portinhola"], datasheet("IP44", "Rev. 05/2025"), review=True)
    assert not any(i["rule_id"] == "EQP-01" for i in validate(api, r1["project"]))


def test_an_old_datasheet_is_a_warning(api: Api, r1: dict[str, Any]) -> None:
    add_sheet(api, r1["portinhola"], datasheet("IP55 IK10", "Rev. 01/2019"), review=False)

    issues = validate(api, r1["project"])

    [old] = [i for i in issues if i["rule_id"] == "EQP-02"]
    assert old["severity"] == "warning" and "01/2019" in old["message"]


def test_the_chosen_alternative_is_the_one_checked(
    api: Api, r1: dict[str, Any], db: Session
) -> None:
    approve_supply(db)
    box = db.scalars(select(Equipment).where(Equipment.reference == "+302")).one()
    box.category = "portinhola"  # an alternative of the same category, for the test
    db.commit()
    add_sheet(api, str(box.id), datasheet("IP66 IK10 Icc 25 kA", "Rev. 05/2025"), review=True)
    pe = db.scalars(select(ProjectEquipment).where(
        ProjectEquipment.default_equipment_id == uuid.UUID(r1["portinhola"]))).one()  # fmt: skip
    chosen = api.as_("tecnico").put(f"/api/project-equipment/{pe.id}",
                                    json={"equipment_id": str(box.id),
                                          "reason": "Portinhola existente na obra."})  # fmt: skip
    assert chosen.status_code == 200, chosen.text

    issues = validate(api, r1["project"])

    assert not any(i["rule_id"] == "EQP-01" for i in issues)
    assert chosen.json()["verdict"] == "ok"
