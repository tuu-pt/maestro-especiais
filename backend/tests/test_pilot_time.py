"""Pilot (Phase 8): active time per step, from the heartbeats of the frontend."""

import uuid

import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record
from app.auth import DEV_USERS
from app.models import PilotTime, Project
from app.pilot.steps import step_for


def make_project(db: Session) -> Project:
    project = Project(code="P8", name="Projeto do piloto", building_type="moradia unifamiliar")
    db.add(project)
    db.flush()
    return project


def beat(api: Api, project: Project, screen: str, hint: str | None = None,
         seconds: int = 30, login: str = "redator") -> int:  # fmt: skip
    body = {"screen": screen, "seconds": seconds, **({"hint": hint} if hint else {})}
    return api.as_(login).post(f"/api/projects/{project.id}/pilot/heartbeat", json=body).status_code


def seconds(db: Session) -> dict[tuple[str, str], int]:
    return {(r.user_id, r.step): r.seconds for r in db.scalars(select(PilotTime))}


@pytest.mark.parametrize(("screen", "hint", "step"), [
    ("ficheiros", None, "dados"), ("ficha", None, "ficha"), ("documentos", "cte", "cte"),
    ("documentos", "formularios", "formularios"), ("documentos", None, "mdj"),
    ("validacao", None, "verificacao"), ("equipamentos", None, "verificacao"),
    ("revisao", None, "conjunto"), ("definicoes", None, None), ("documentos", "lixo", "mdj"),
    ("validacao", "formularios", "verificacao"),  # a hint left from the editor does not count
])  # fmt: skip
def test_each_screen_is_one_of_the_eight_steps(screen: str, hint: str | None, step: str) -> None:
    assert step_for(screen, hint, reviewed=False) == step


def test_after_the_review_request_editing_counts_as_corrections() -> None:
    assert step_for("documentos", "mdj", reviewed=True) == "correcoes"
    assert step_for("ficha", None, reviewed=True) == "correcoes"
    assert step_for("validacao", None, reviewed=True) == "verificacao"
    assert step_for("revisao", None, reviewed=True) == "conjunto"


def test_heartbeats_add_up_per_person_and_step(api: Api, db: Session) -> None:
    project = make_project(db)

    for _ in range(3):
        assert beat(api, project, "documentos", "mdj") == 204
    beat(api, project, "documentos", "mdj", login="tecnico")
    beat(api, project, "definicoes")  # not a step: nothing

    assert seconds(db) == {("dev:redator", "mdj"): 90, ("dev:tecnico", "mdj"): 30}


def test_one_heartbeat_never_adds_more_than_a_minute(api: Api, db: Session) -> None:
    project = make_project(db)

    beat(api, project, "ficha", seconds=3600)

    assert seconds(db) == {("dev:redator", "ficha"): 60}


def test_edits_after_the_review_request_are_corrections(api: Api, db: Session) -> None:
    project = make_project(db)
    record(db, DEV_USERS["tecnico"], "review.requested", "project", project.id,
           {"documents": 2}, project_id=project.id)  # fmt: skip
    db.flush()

    beat(api, project, "documentos", "cte")
    beat(api, project, "revisao")

    assert seconds(db) == {("dev:redator", "correcoes"): 30, ("dev:redator", "conjunto"): 30}


def test_unknown_project_and_no_session(api: Api, db: Session) -> None:
    unknown = api.as_("redator").post(f"/api/projects/{uuid.uuid4()}/pilot/heartbeat",
                                      json={"screen": "ficha"})  # fmt: skip
    assert unknown.status_code == 404
    assert beat(api, make_project(db), "ficha", login="") == 401
