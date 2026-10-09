"""Pilot (Phase 8): the estimate of the manual process per project, and the problems found."""

from typing import Any

import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, PilotNote, Project

ESTIMATE = {"steps": {"mdj": [120, 180], "cte": [90, 120], "formularios": [30, 45]},
            "rounds": 2, "errors": "Potência diferente entre a MDJ e a ficha.",
            "typology": "habitação unifamiliar"}  # fmt: skip


@pytest.fixture
def project(db: Session) -> Project:
    p = Project(code="P8", name="Projeto do piloto", building_type="moradia unifamiliar")
    db.add(p)
    db.flush()
    return p


def put(api: Api, project: Project, body: dict[str, Any], login: str = "tecnico") -> Any:
    return api.as_(login).put(f"/api/projects/{project.id}/pilot/baseline", json=body)


@pytest.mark.parametrize(("login", "code"), [("tecnico", 200), ("admin", 200),
                                             ("redator", 403), ("curador", 403)])  # fmt: skip
def test_the_technician_or_the_admin_writes_the_estimate(
    api: Api, project: Project, login: str, code: int
) -> None:
    assert put(api, project, ESTIMATE, login).status_code == code


def test_the_estimate_is_kept_replaced_and_audited(api: Api, db: Session, project: Project) -> None:
    put(api, project, ESTIMATE)

    body = put(api, project, {**ESTIMATE, "rounds": 3}).json()

    assert body["steps"]["mdj"] == [120, 180] and body["rounds"] == 3
    assert body["updated_by"] == "dev:tecnico"
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "pilot.baseline")).all()
    assert len(events) == 2 and events[0].payload["steps"] == ["cte", "formularios", "mdj"]


@pytest.mark.parametrize("steps", [{"mdj": [180, 120]}, {"cafe": [1, 2]}, {"mdj": [-1, 2]}])
def test_minutes_in_order_and_known_steps(
    api: Api, project: Project, steps: dict[str, list[int]]
) -> None:
    assert put(api, project, {"steps": steps}).status_code == 422


def test_anyone_writes_a_problem_with_the_step_of_the_screen(
    api: Api, db: Session, project: Project
) -> None:
    body = {"text": "O bloco da introdução repete a obra.", "screen": "documentos",
            "hint": "cte", "project_id": str(project.id)}  # fmt: skip

    created = api.as_("redator").post("/api/pilot/notes", json=body)

    assert created.status_code == 201
    note = created.json()
    assert (note["step"], note["status"], note["created_by"]) == ("cte", "open", "dev:redator")
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "pilot.note")).one()
    assert "text" not in event.payload  # the text stays in the note, never in the audit


def test_a_problem_without_project_and_the_list(api: Api, project: Project) -> None:
    api.as_("curador").post("/api/pilot/notes", json={"text": "Alerta errado.", "screen": ""})
    api.as_("redator").post("/api/pilot/notes", json={"text": "Do projeto.", "screen": "ficha",
                                                       "project_id": str(project.id)})  # fmt: skip

    everything = api.as_("redator").get("/api/pilot/notes").json()
    mine = api.as_("redator").get("/api/pilot/notes", params={"project": str(project.id)}).json()

    assert len(everything) == 2 and [n["text"] for n in mine] == ["Do projeto."]
    assert mine[0]["step"] == "ficha"


def test_only_the_admin_or_the_curator_marks_it_resolved(
    api: Api, db: Session, project: Project
) -> None:
    body = {"text": "Alerta errado.", "screen": "validacao"}
    note = api.as_("redator").post("/api/pilot/notes", json=body).json()
    path = f"/api/pilot/notes/{note['id']}"

    assert api.as_("redator").patch(path, json={"status": "resolved"}).status_code == 403
    resolved = api.as_("curador").patch(path, json={"status": "resolved"}).json()

    assert resolved["status"] == "resolved" and resolved["resolved_by"] == "dev:curador"
    assert db.scalars(select(PilotNote)).one().resolved_at is not None
