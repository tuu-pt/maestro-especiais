"""Pilot (Phase 8): time against the estimate, incoherences at approval, the goal and the report."""

from datetime import UTC, date, datetime, timedelta

import pytest
from conftest import Api
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentRevision,
    FichaRevision,
    FichaValue,
    PilotBaseline,
    PilotNote,
    PilotTime,
    Project,
    ValidationIssue,
    ValidationRun,
)
from app.pilot.metrics import project_metrics
from app.pilot.report import LEFT_OUT, render

T0 = datetime(2026, 10, 9, 9, 0, tzinfo=UTC)


@pytest.fixture
def project(db: Session) -> Project:
    p = Project(code="P8", name="Moradia Particular do Senhor X", building_type="moradia")
    db.add(p)
    db.flush()
    return p


def time(db: Session, project: Project, step: str, minutes: int, user: str = "dev:tecnico") -> None:
    db.add(PilotTime(project_id=project.id, user_id=user, step=step, day=date(2026, 10, 9),
                     seconds=minutes * 60))  # fmt: skip
    db.flush()


def estimate(db: Session, project: Project) -> None:
    db.add(PilotBaseline(project_id=project.id, typology="habitação unifamiliar", rounds=2,
                         steps={"mdj": [100, 140], "cte": [80, 100], "formularios": [20, 40],
                                "ficha": [30, 30]}))  # fmt: skip
    db.flush()


def run(db: Session, project: Project, at: datetime, issues: list[tuple[str, str, str]]) -> None:
    r = ValidationRun(project_id=project.id, status="done", finished_at=at)
    db.add(r)
    db.flush()
    for n, (rule, fingerprint, status) in enumerate(issues):
        db.add(ValidationIssue(run_id=r.id, order=n, rule_id=rule, severity="critical",
                               category="coherence", fingerprint=fingerprint, message_pt="x",
                               status=status))  # fmt: skip
    db.flush()


def approve(db: Session, project: Project, kind: str, at: datetime, number: int = 0) -> None:
    ficha = FichaRevision(project_id=project.id, label=kind, status="confirmed")
    db.add(ficha)
    db.flush()
    doc = Document(project_id=project.id, type=kind, ficha_revision_id=ficha.id, status="approved")
    db.add(doc)
    db.flush()
    db.add(DocumentRevision(document_id=doc.id, number=number, approved_by="dev:tecnico",
                            approved_at=at))  # fmt: skip
    db.flush()


def test_time_per_step_against_the_middle_of_the_estimate(db: Session, project: Project) -> None:
    estimate(db, project)
    time(db, project, "mdj", 40)
    time(db, project, "mdj", 20, user="dev:redator")  # two people: summed
    time(db, project, "cte", 30)
    time(db, project, "formularios", 6)
    time(db, project, "verificacao", 15)  # no estimate: out of the reduction

    m = project_metrics(db, project)

    rows = {r.step: (r.seconds, r.estimate) for r in m.steps}
    assert rows["mdj"] == (3600, (100, 140)) and rows["dados"] == (0, None)
    assert m.reduction(("mdj", "cte", "formularios")) == pytest.approx(1 - 96 / 240)
    assert m.goal["time_ok"] and not m.goal["approved"] and not m.goal["met"]
    assert m.typology == "habitação unifamiliar" and m.rounds_estimate == 2


def test_incoherences_found_and_left_at_each_approval(db: Session, project: Project) -> None:
    estimate(db, project)
    time(db, project, "mdj", 30)
    run(db, project, T0, [("COE-05", "pot", "open"), ("COE-06", "cabo", "open"),
                          ("COE-01", "quadros", "open")])  # fmt: skip
    run(db, project, T0 + timedelta(hours=1), [("COE-06", "cabo", "ignored")])
    approve(db, project, "MDJ", T0 + timedelta(hours=2))
    run(db, project, T0 + timedelta(hours=3), [])  # after the approval: does not count
    approve(db, project, "CTE", T0 + timedelta(hours=4))

    m = project_metrics(db, project)

    mdj, cte = m.approvals
    assert mdj.groups["potencia"] == {"found": 1, "open": 0, "ignored": 0}
    assert mdj.groups["cabos"] == {"found": 1, "open": 0, "ignored": 1}
    assert mdj.groups["identificacao"] == {"found": 0, "open": 0, "ignored": 0}
    assert not mdj.clean and cte.clean  # an ignored cable at the MDJ's approval
    assert not m.goal["coherent"] and not m.goal["met"]


def test_the_goal_is_met_with_the_time_and_clean_approvals(db: Session, project: Project) -> None:
    estimate(db, project)
    time(db, project, "mdj", 50)
    run(db, project, T0, [("COE-04", "obra", "open")])
    run(db, project, T0 + timedelta(hours=1), [])  # corrected
    approve(db, project, "MDJ", T0 + timedelta(hours=2))

    goal = project_metrics(db, project).goal

    assert goal == {**goal, "time_ok": True, "approved": True, "coherent": True, "met": True}


def test_the_report_has_numbers_and_never_personal_data(db: Session, project: Project) -> None:
    estimate(db, project)
    time(db, project, "cte", 45)
    ficha = FichaRevision(project_id=project.id, label="A", status="confirmed")
    db.add(ficha)
    db.flush()
    db.add(FichaValue(revision_id=ficha.id, key="id.requerente.nome", group="identificacao",
                      label_pt="Requerente", value="Joana Exemplo Teste", personal_data=True,
                      source_type="manual"))  # fmt: skip
    for text in (
        "O bloco da introdução repete a obra.",
        "Ligar à Joana Exemplo Teste.",
        "Escrever para pessoa@exemplo.test sobre o CTE.",
    ):
        db.add(PilotNote(project_id=project.id, screen="documentos", step="cte", text=text,
                         status="open"))  # fmt: skip
    db.flush()

    text = render(db, today=T0)

    assert "## P8 · habitação unifamiliar" in text and "| Escrever o CTE | 45 min |" in text
    assert "O bloco da introdução repete a obra." in text
    assert "Joana" not in text and "pessoa@exemplo.test" not in text and LEFT_OUT in text
    assert "•••" in text  # the email masked, the rest of the note kept
    assert project.name not in text


def test_the_screens_of_the_pilot(api: Api, db: Session, project: Project) -> None:
    estimate(db, project)
    time(db, project, "mdj", 10)

    mine = api.as_("redator").get(f"/api/projects/{project.id}/pilot").json()
    summary = api.as_("redator").get("/api/pilot/summary").json()

    assert mine["code"] == "P8" and mine["baseline"]["steps"]["mdj"] == [100, 140]
    assert mine["notes"] == [] and mine["goal"]["approved"] is False
    assert [p["code"] for p in summary] == ["P8"]


def test_an_empty_pilot(db: Session) -> None:
    assert "Ainda não há projetos com tempo medido" in render(db, today=T0)
