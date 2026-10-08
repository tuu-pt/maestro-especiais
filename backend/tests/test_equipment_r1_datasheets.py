"""Criterion of Phase 7: the reference equipment of R1 with its manufacturer's datasheet, read and
checked against the CTE (data/fixtures/fichas-tecnicas/R1). With --fichas-report=<path> it also
writes docs/fase7-fichas-R1.md (make fichas-report).

The curator is simulated: every parameter read from a datasheet is taken as reviewed and every
requirement of the CTE as approved, so the checks are the ones a reviewed library would give.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from reference_projects import FIXTURES, load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.equipment.datasheets import current, seed_datasheets
from app.equipment.report import report, summary
from app.models import Document, Equipment, EquipmentParam, Requirement
from app.storage import ObjectStore

SHEETS = FIXTURES / "fichas-tecnicas" / "R1"
INTRO = [
    "# Fase 7 · Equipamentos de R1 contra as fichas técnicas",
    "",
    "Gerado por `make fichas-report` (backend/tests/test_equipment_r1_datasheets.py). As fichas",
    "são as dos fabricantes em `data/fixtures/fichas-tecnicas/R1/` (`fichas.json` diz a origem de",
    "cada uma). Para mostrar a verificação que uma biblioteca revista daria, o teste toma **todos",
    "os parâmetros lidos como revistos e todos os requisitos do CTE como aprovados**: na",
    "aplicação, isso é o curador que decide (D7). A tensão é só informação (não é requisito):",
    "as fichas listam alimentações, gamas e correntes de relés.",
]
pytestmark = [
    pytest.mark.usefixtures("inline_ingestion"),
    pytest.mark.skipif(not (SHEETS / "fichas.json").is_file(), reason="sem fichas técnicas de R1"),
]


def item(db: Session, **where: Any) -> Equipment:
    query = select(Equipment)
    for k, v in where.items():
        query = query.where(getattr(Equipment, k) == v)
    return db.scalars(query).one()


def read(db: Session, e: Equipment) -> dict[str, set[Any]]:
    sheet = current(e)
    assert sheet is not None, e.name
    out: dict[str, set[Any]] = {}
    for p in e.params:
        if p.datasheet_id == sheet.id:
            out.setdefault(p.name, set()).add(p.value)
    return out


@pytest.fixture
def seeded(db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    found = seed_datasheets(db, store, SHEETS)
    db.commit()
    return found


def test_every_datasheet_is_linked_to_its_equipment(
    db: Session, store: ObjectStore, seeded: dict[str, Any]
) -> None:
    manifest = json.loads((SHEETS / "fichas.json").read_text(encoding="utf-8"))
    links = sum(len(f["equipamentos"]) for f in manifest["fichas"])

    assert seeded["datasheets_unmatched"] == []
    assert seeded["datasheets"] == links
    assert seed_datasheets(db, store, SHEETS)["datasheets"] == 0  # the same files: nothing new


def test_what_is_read_from_the_real_datasheets(db: Session, seeded: dict[str, Any]) -> None:
    quadro = "+34929 CX QUADRO (5x24) 120md P200 INT"
    board = read(db, item(db, manufacturer="Quitérios", model=quadro))
    assert board["ip_rating"] == {"IP54"} and board["ik_rating"] == {"IK07"}
    box = item(db, manufacturer="JSL", model="J80-M")
    assert {"IP55", "IP66"} <= read(db, box)["ip_rating"] and read(db, box)["ik_rating"] == {"IK08"}
    sheet = current(box)
    assert sheet is not None and sheet.issue_date == date(2020, 1, 3)  # «DATA / DATE: 2020.01.03»
    detector = read(db, item(db, manufacturer="PERRY", model="1SP SP020"))
    assert 360.0 in detector["detection_angle_deg"] and detector["ip_rating"] == {"IP20"}
    assert read(db, item(db, manufacturer="EFAPEL", reference="48132 C"))["ip_rating"] == {"IP65"}


def test_the_equipment_of_r1_checked_against_the_cte(
    api: Api, db: Session, seeded: dict[str, Any], request: pytest.FixtureRequest
) -> None:
    project_id = load_confirmed(api, "R1")
    made = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "CTE"})
    assert made.status_code == 201, made.text
    now = datetime.now(UTC)
    for p in db.scalars(select(EquipmentParam).where(EquipmentParam.origin == "datasheet")):
        p.review_status, p.reviewed_by, p.reviewed_at = "reviewed", "dev:curador", now
    for r in db.scalars(select(Requirement)):
        r.status = "approved"
    db.commit()
    document = db.get(Document, made.json()["id"])
    assert document is not None

    found = summary(db, document)
    manifest = json.loads((SHEETS / "fichas.json").read_text(encoding="utf-8"))
    text = report(db, document, INTRO, manifest["sem_ficha"])

    assert (found["slots"], found["with_datasheet"]) == (32, 20)
    assert found["verdicts"]["fails"] == 0  # nothing of R1 fails its CTE with the real sheets
    assert found["verdicts"]["ok"] >= 5  # the boards, the detectors, the indoor station
    assert "Detetores de movimento de 360º (PERRY 1SP SP020) |" in text
    assert "Alcance de deteção ≥ 14 m → cumpre (14 m)" in text
    path = request.config.getoption("--fichas-report")
    if path:
        Path(path).write_text(text, encoding="utf-8")
