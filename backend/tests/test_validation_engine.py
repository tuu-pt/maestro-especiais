"""Validation engine (Phase 5, task 1): runs, issues, decisions kept, likely reading."""

import uuid
from typing import Any, cast

import pytest
from conftest import Api, Published, RecordingQueue
from reference_projects import load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AuditEvent, Circuit, FichaRevision, PieceFacts
from app.storage import ObjectStore
from app.validation.context import Context
from app.validation.engine import run_validation
from app.validation.likely import Observation, reading, split
from app.validation.normalize import number, same
from app.validation.pieces import Fact, Paragraph, Piece, PieceData
from app.validation.rules import all_rules, num_01

pytestmark = pytest.mark.usefixtures("inline_ingestion")


@pytest.fixture
def inline_validation(
    db: Session, store: ObjectStore, settings: Settings, published: Published,
    validation_queue: RecordingQueue,
) -> None:  # fmt: skip
    def run(run_id: uuid.UUID) -> None:
        run_validation(db, store, settings, published, run_id)

    validation_queue.run = run


@pytest.fixture
def r1(api: Api, db: Session, store: ObjectStore) -> str:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    made = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
    assert made.status_code in (200, 201), made.text
    return project_id


def validate(api: Api, project_id: str) -> dict[str, Any]:
    started = api.as_("redator").post(f"/api/projects/{project_id}/validation", json={})
    assert started.status_code == 202, started.text
    out: dict[str, Any] = api.as_("redator").get(f"/api/projects/{project_id}/validation").json()
    return out


def break_a_circuit(db: Session, project_id: str) -> Circuit:
    revision = db.scalars(select(FichaRevision).where(
        FichaRevision.project_id == project_id, FichaRevision.status == "confirmed"
    )).one()  # fmt: skip
    circuit = next(c for c in revision.circuits if c.iz145_a is not None)
    assert circuit.iz145_a is not None
    circuit.i2_a = circuit.iz145_a + 1
    db.commit()
    return circuit


# ---------------------------------------------------------------- engine and API


def test_validation_needs_a_confirmed_ficha_base(api: Api) -> None:
    project = api.as_("redator").post("/api/projects", json={"code": "V0", "name": "V0"}).json()

    response = api.as_("redator").post(f"/api/projects/{project['id']}/validation", json={})
    state = api.as_("redator").get(f"/api/projects/{project['id']}/validation").json()

    assert response.status_code == 409 and "ficha-base confirmada" in response.json()["detail"]
    assert state["ready"] is False and state["run"] is None and state["issues"] == []


@pytest.mark.usefixtures("inline_validation")
def test_a_run_reads_the_pieces_runs_every_rule_and_keeps_the_issues(
    api: Api, db: Session, r1: str, published: Published
) -> None:
    circuit = break_a_circuit(db, r1)

    state = validate(api, r1)

    run = state["run"]
    assert run["status"] == "done" and run["totals"]["rules"] == len(all_rules())
    assert run["totals"]["rules_failed"] == [] and run["totals"]["pieces"] >= 1
    assert {p["kind"] for p in run["pieces"]} >= {"MDJ"}
    cal = [i for i in state["issues"] if i["rule_id"] == "CAL-01"]
    assert len(cal) == 1 and cal[0]["severity"] == "warning" and cal[0]["new"]
    assert circuit.destination in cal[0]["message"] and "I2 ≤ 1,45·Iz" in cal[0]["message"]
    assert cal[0]["likely_reading"] == "Confirmar na folha de cálculo."
    assert "ignore" in cal[0]["actions"] and "confirm_sheet" in cal[0]["actions"]
    steps = [e.get("step") for _, e in published if e.get("type") == "validation"]
    assert "A correr as regras" in steps
    assert db.scalar(select(PieceFacts).where(PieceFacts.project_id == r1)) is not None


@pytest.mark.usefixtures("inline_validation")
def test_ignoring_needs_a_justification_and_survives_the_next_run(
    api: Api, db: Session, r1: str
) -> None:
    break_a_circuit(db, r1)
    issue = next(i for i in validate(api, r1)["issues"] if i["rule_id"] == "CAL-01")
    client = api.as_("tecnico")

    short = client.post(f"/api/validation/issues/{issue['id']}/ignore", json={"reason": "ok"})
    done = client.post(f"/api/validation/issues/{issue['id']}/ignore",
                       json={"reason": "Valor confirmado na folha de cálculo."})  # fmt: skip
    again = next(i for i in validate(api, r1)["issues"] if i["rule_id"] == "CAL-01")

    assert short.status_code == 422
    assert done.status_code == 200 and done.json()["status"] == "ignored"
    assert again["status"] == "ignored" and not again["new"]
    assert again["ignored_reason"] == "Valor confirmado na folha de cálculo."
    actions = db.scalars(select(AuditEvent.action).where(
        AuditEvent.entity_id == done.json()["id"])).all()  # fmt: skip
    assert "validation.issue_ignored" in actions


@pytest.mark.usefixtures("inline_validation")
def test_an_issue_not_found_again_is_fixed_and_the_cache_is_reused(
    api: Api, db: Session, r1: str
) -> None:
    circuit = break_a_circuit(db, r1)
    first = validate(api, r1)
    circuit.i2_a = circuit.iz145_a
    db.commit()

    second = validate(api, r1)

    assert not [i for i in second["issues"] if i["rule_id"] == "CAL-01"]
    assert second["run"]["totals"]["reread"] == 0  # no piece changed: read from the cache
    old = next(i for i in first["issues"] if i["rule_id"] == "CAL-01")
    fixed = api.as_("redator").get(f"/api/projects/{r1}/validation",
                                   params={"status": "fixed"}).json()  # fmt: skip
    assert fixed["issues"] == []  # the filter applies to the last run only
    assert old["id"] not in {i["id"] for i in second["issues"]}


def test_an_edit_queues_a_revalidation_of_the_changed_pieces(
    api: Api, db: Session, r1: str, validation_queue: RecordingQueue
) -> None:
    validation_queue.run = None
    validate(api, r1)  # queued, not run: no finished run yet
    doc = api.as_("redator").get(f"/api/projects/{r1}/documents").json()[0]
    fresh = api.as_("redator").get(f"/api/documents/{doc['id']}").json()
    section = next(s for s in fresh["sections"] if s["kind"] == "block" and not s["locked"])
    before = len(validation_queue.enqueued)

    api.as_("redator").put(f"/api/sections/{section['id']}/content",
                           json={"content": section["content"]})  # fmt: skip

    assert len(validation_queue.enqueued) == before  # never validated: nothing to revalidate


@pytest.mark.usefixtures("inline_validation")
def test_after_a_validation_an_edit_revalidates_only_what_changed(
    api: Api, r1: str, validation_queue: RecordingQueue
) -> None:
    validate(api, r1)
    doc = api.as_("redator").get(f"/api/projects/{r1}/documents").json()[0]
    fresh = api.as_("redator").get(f"/api/documents/{doc['id']}").json()
    section = next(s for s in fresh["sections"] if s["kind"] == "block" and not s["locked"])
    before = len(validation_queue.enqueued)

    api.as_("redator").put(f"/api/sections/{section['id']}/content",
                           json={"content": section["content"]})  # fmt: skip
    state = api.as_("redator").get(f"/api/projects/{r1}/validation").json()

    assert len(validation_queue.enqueued) == before + 1
    assert state["current"]["trigger"] == "changed" and state["current"]["status"] == "done"
    assert state["run"]["totals"]["reread"] == 1  # only the edited MDJ was read again


# ---------------------------------------------------------------- likely reading


def _piece(kind: str, date: str | None = None) -> Piece:
    return Piece(ref=f"file:{kind}", kind=kind, origin="file", content_hash="x", date=date)


def _obs(kind: str, value: Any, date: str | None = None) -> Observation:
    return Observation(_piece(kind, date), Fact("k", value, f"file:{kind}"))


def test_only_one_piece_differs_so_it_is_the_suspect() -> None:
    d = split(200, [_obs("FICHA_ELE", 180), _obs("CTE", 200), _obs("CALC", "200,0")], same)

    assert [o.piece.kind for o in d.divergent] == ["FICHA_ELE"]
    assert reading(d, "2026-09-28") == "Erro provável na ficha eletrotécnica."


def test_a_piece_newer_than_the_ficha_makes_the_ficha_the_suspect() -> None:
    d = split(5, [_obs("CTE", 6, "2026-10-02"), _obs("MDJ", 5)], same)

    text = reading(d, "2026-09-28")

    assert text is not None and text.startswith("CTE é mais recente do que a ficha-base")
    assert "propor atualizar a ficha" in text


def test_several_pieces_differing_is_never_decided_by_majority() -> None:
    d = split(180, [_obs("CTE", 200), _obs("CALC", 200), _obs("MDJ", 180)], same)

    assert reading(d, None) == (
        "Várias peças divergem da ficha-base (CTE, Tabela de Cálculo): confirmar a ficha-base e "
        "cada peça."
    )
    assert reading(split(5, [_obs("MDJ", 5)], same), None) is None


@pytest.mark.parametrize(
    ("a", "b", "equal"),
    [("34,5", 34.5, True), ("1.234,5", "1234.5", True), ("200", "200,0", True),
     ("H07V-U", "h07v-u", True), ("Rua da Sé.", "rua da se", True), (5, 6, False)],
)  # fmt: skip
def test_values_are_compared_without_computing(a: Any, b: Any, equal: bool) -> None:
    assert same(a, b) is equal
    assert number("7,4") == 7.4 and number("kVA") is None


# ---------------------------------------------------------------- NUM-01 as a rule


def test_num_01_flags_only_the_text_of_the_agent() -> None:
    piece = Piece(ref="doc:1", kind="MDJ", origin="assembled", content_hash="x")
    agent = Paragraph(
        "doc:1",
        "canalizacoes",
        "Canalizações",
        "block",
        0,
        "Tomadas a 16 A a 250 V.",
        "Tomadas a 16 A a 250 V.",
        generated=True,
    )
    person = Paragraph("doc:1", "canalizacoes", "Canalizações", "block", 1,
                       "Afastamento de 20 cm.", "Afastamento de 20 cm.")  # fmt: skip
    ctx = Context(cast(Any, None), cast(Any, None), cast(Any, None), {"doc:1": piece},
                  {"doc:1": PieceData(paragraphs=[agent, person])})  # fmt: skip

    found = num_01.RULE.check(ctx)

    assert {f.location["paragraph"] for f in found} == {0}
    assert all(f.rule_id == "NUM-01" for f in found)
