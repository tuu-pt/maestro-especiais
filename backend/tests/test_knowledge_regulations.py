"""Regulation corpus (Annex D): references only, all "a confirmar" and not citable (task 6)."""

from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.knowledge.regulations import COPYRIGHT_NOTE, CORPUS
from app.knowledge.seed import seed_knowledge
from app.models import RegulationDoc

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"


@pytest.fixture
def seeded(db: Session) -> dict[str, int]:
    if not (FIXTURES / "R1").is_dir() or not (FIXTURES / "R2").is_dir():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    return seed_knowledge(db, FIXTURES)


def doc(db: Session, code: str) -> RegulationDoc:
    return db.scalars(select(RegulationDoc).where(RegulationDoc.code == code)).one()


def test_the_annex_d_list_starts_to_be_confirmed_and_not_citable(
    db: Session, seeded: dict[str, int]
) -> None:
    rows = db.scalars(select(RegulationDoc)).all()

    assert seeded["regulations"] == len(rows) == len(CORPUS) == 14
    assert all(r.review_status == "proposed" and not r.citable and r.status is None for r in rows)
    assert all(r.specialties == ["ele"] for r in rows)


def test_standards_under_copyright_keep_only_title_and_scope(
    db: Session, seeded: dict[str, int]
) -> None:
    standards = [r for r in db.scalars(select(RegulationDoc)) if r.kind == "norma"]

    assert {r.code for r in standards} >= {"np-en-60529", "np-en-50102", "en-60898", "en-12464-1"}
    assert all(r.copyrighted and r.license_note == COPYRIGHT_NOTE for r in standards)
    assert all(len(r.scope) < 120 for r in standards)
    # there is no column for the text of a document: full-text search is future work
    columns = {c.key for c in inspect(RegulationDoc).columns}
    assert not {"text", "body", "content", "chunks"} & columns


def test_each_reference_says_where_r1_and_r2_cite_it(db: Session, seeded: dict[str, int]) -> None:
    rtiebt = doc(db, "rtiebt")
    assert rtiebt.found_count > 10
    pairs = {(f["project"], f["source"]) for f in rtiebt.found_in}
    assert pairs == {
        ("R1", "MDJ"),
        ("R1", "CTE"),
        ("R2", "MDJ"),
        ("R2", "CTE"),
    }  # the sample covers all
    assert "RTIEBT" in rtiebt.found_in[0]["text"]
    assert {f["project"] for f in doc(db, "dl-96-2017").found_in} == {"R1"}  # in the forms of R1
    assert doc(db, "dl-96-2017").found_in[0]["source"] == "Formulário"
    assert doc(db, "guia-dgeg-ve").found_count >= 2
    # the SPEC lists them, the reference documents do not cite them: the curator decides
    assert doc(db, "despacho-dgeg-1-2018").found_count == 0
    assert doc(db, "portaria-701-h-2008").found_count == 0


def test_seeding_again_keeps_the_curator_decision(db: Session, seeded: dict[str, int]) -> None:
    rtiebt = doc(db, "rtiebt")
    rtiebt.review_status, rtiebt.status, rtiebt.edition = (
        "confirmed",
        "in_force",
        "2006, na redação de 2022",
    )
    db.flush()

    seed_knowledge(db, FIXTURES)

    db.refresh(rtiebt)
    assert (rtiebt.review_status, rtiebt.edition) == ("confirmed", "2006, na redação de 2022")


# ---------------------------------------------------------------- API


def listed(api: Api, login: str = "redator") -> dict[str, dict[str, Any]]:
    return {r["code"]: r for r in api.as_(login).get("/api/knowledge/regulations").json()}


def test_empty_corpus(api: Api) -> None:
    assert listed(api) == {}


@pytest.mark.parametrize("login", ["redator", "tecnico", "admin"])
def test_only_a_curator_confirms(api: Api, seeded: dict[str, int], login: str) -> None:
    rtiebt = listed(api)["rtiebt"]
    response = api.as_(login).post(
        f"/api/knowledge/regulations/{rtiebt['id']}/review",
        json={"decision": "confirmed", "status": "in_force"},
    )
    assert response.status_code == 403


def test_the_curator_confirms_then_marks_citable(api: Api, seeded: dict[str, int]) -> None:
    rtiebt = listed(api)["rtiebt"]
    base = f"/api/knowledge/regulations/{rtiebt['id']}"
    curator = api.as_("curador")

    early = curator.post(f"{base}/citable", json={"citable": True})
    assert early.status_code == 422
    assert (
        early.json()["detail"]
        == "Só um documento confirmado pelo curador e em vigor pode ser citado."
    )
    no_status = curator.post(f"{base}/review", json={"decision": "confirmed"})
    assert no_status.status_code == 422

    confirmed = curator.post(
        f"{base}/review",
        json={"decision": "confirmed", "status": "in_force", "edition": "redação atual"},
    ).json()
    assert (confirmed["review_status"], confirmed["status"], confirmed["citable"]) == (
        "confirmed", "in_force", False,
    )  # fmt: skip
    assert confirmed["last_checked_at"] and confirmed["reviewed_by"] == "dev:curador"
    citable = curator.post(f"{base}/citable", json={"citable": True}).json()
    assert citable["citable"] is True

    revoked = curator.post(
        f"{base}/review", json={"decision": "confirmed", "status": "revoked"}
    ).json()
    assert revoked["citable"] is False  # a revoked document is never citable

    activity = [e["description"] for e in api.as_("redator").get("/api/activity").json()]
    assert activity[:3] == [
        f"Confirmou «{rtiebt['title']}» (revogado)",
        f"Marcou «{rtiebt['title']}» como citável",
        f"Confirmou «{rtiebt['title']}» (em vigor)",
    ]


def test_rejecting_a_reference(api: Api, seeded: dict[str, int]) -> None:
    portaria = listed(api)["portaria-701-h-2008"]

    rejected = (
        api.as_("curador")
        .post(
            f"/api/knowledge/regulations/{portaria['id']}/review",
            json={"decision": "rejected", "note": "Não se aplica a obras particulares."},
        )
        .json()
    )

    assert rejected["review_status"] == "rejected" and not rejected["citable"]
    assert rejected["review_note"] == "Não se aplica a obras particulares."
