"""Cable dictionary and typology lexicon: normalization, seed from R1/R2, curator-only decisions."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge import cables, seed
from app.knowledge.seed import seed_knowledge
from app.models import CableDesignation, CableEquivalence, SourceDocument, Typology
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"


@pytest.mark.parametrize(
    ("text", "family", "geometry"),
    [
        ("RZ1-K (AS) 5G10mm2", "RZ1-K (AS)", "5G10"),
        ("XZ1 (frt, zh) 5G10 mm²", "XZ1(frt,zh)", "5G10"),
        ("XZ1(frt,zh) 5G2,5mm²", "XZ1(frt,zh)", "5G2,5"),
        ("XAV 4(1x185)mm²", "XAV", "4x1x185"),
        ("XAV 4x1x185mm²", "XAV", "4x1x185"),
        ("3x H07V-U 10mm²", "H07V-U", "3x10"),
        ("H07V\u2011K - 2,5mm²", "H07V-K", "1x2,5"),  # a non-breaking hyphen, as in Word
        ("RV-K 4x16m²", "RV-K", "4x16"),  # "m²" typed for "mm²"
        ("FXZ1 em caminhos de cabos", "FXZ1", None),
    ],
)
def test_writing_variants_are_the_same_designation(
    text: str, family: str, geometry: str | None
) -> None:
    [found] = cables.find(text)
    assert (found.family, found.geometry) == (family, geometry)


def test_xv_needs_a_cable_context() -> None:
    assert [d.family for d in cables.find("cabos XV ou RV-K.")] == ["XV", "RV-K"]
    assert cables.find("no século XV") == []


def test_rigid_and_flexible_are_never_equivalent() -> None:
    assert cables.flexible("H07V-U") is False and cables.flexible("H07V-K") is True
    assert not cables.may_be_equivalent("H07V-U", "H07V-K")
    assert not cables.may_be_equivalent("H07V-R", "RV-K")
    assert not cables.may_be_equivalent("RV-K", "H07V-K")  # a cable and a wire
    assert cables.may_be_equivalent("RZ1-K (AS)", "XZ1(frt,zh)")  # XZ1: the name does not say


# ---------------------------------------------------------------- seed from the fixtures


@pytest.fixture
def seeded(db: Session) -> dict[str, int]:
    if not (FIXTURES / "R1").is_dir() or not (FIXTURES / "R2").is_dir():
        pytest.skip("data/fixtures/R1 e R2 são precisos para semear a base de conhecimento")
    return seed_knowledge(db, FIXTURES)


def family(db: Session, name: str) -> CableDesignation:
    return db.scalars(select(CableDesignation).where(CableDesignation.canonical == name)).one()


def test_every_designation_keeps_its_text_and_where_it_appeared(
    db: Session, seeded: dict[str, int]
) -> None:
    xz1 = family(db, "XZ1(frt,zh)")
    lpu = [o for o in xz1.occurrences if o.source == "LPU"]
    assert lpu and all(o.project_code == "R2" for o in lpu)
    assert any(
        o.raw_text == "XZ1(frt,zh) 5G10mm²" and o.locator.startswith("LPU!linha") for o in lpu
    )
    rz1 = family(db, "RZ1-K (AS)")
    assert {o.source for o in rz1.occurrences} == {"Tabela"}
    assert all(d.status == "proposed" for d in db.scalars(select(CableDesignation)))


def test_c1_both_wires_of_r1_are_listed_and_never_proposed_as_equivalent(
    db: Session, seeded: dict[str, int]
) -> None:
    k, u = family(db, "H07V-K"), family(db, "H07V-U")
    assert {o.source for o in k.occurrences if o.project_code == "R1"} >= {"MDJ", "MQT"}
    assert {o.source for o in u.occurrences if o.project_code == "R1"} >= {"CTE", "Tabela"}
    pairs = {(e.a.canonical, e.b.canonical) for e in db.scalars(select(CableEquivalence))}
    assert ("H07V-K", "H07V-U") not in pairs
    for a, b in pairs:
        assert cables.may_be_equivalent(a, b)


def test_c9_the_names_of_r2_cables_are_evidence_for_a_proposal(
    db: Session, seeded: dict[str, int]
) -> None:
    assert {o.source for o in family(db, "FXZ1").occurrences} >= {"MDJ"}  # C9: MDJ/CTE say FXZ1
    proposal = db.scalars(
        select(CableEquivalence).where(
            CableEquivalence.a_id == family(db, "RZ1-K (AS)").id,
            CableEquivalence.b_id == family(db, "XZ1(frt,zh)").id,
        )
    ).one()
    assert proposal.status == "proposed"
    evidence = proposal.evidence[0]
    assert evidence["project"] == "R2" and evidence["geometry"]
    assert {evidence["a"]["source"], evidence["b"]["source"]} == {"Tabela", "LPU"}


def test_typologies_and_incompatible_terms_with_c2_as_evidence(
    db: Session, seeded: dict[str, int]
) -> None:
    moradia = db.scalars(select(Typology).where(Typology.name == "moradia unifamiliar")).one()
    assert any(e["project"] == "R1" for e in moradia.evidence)
    terms = {t.term: t for t in moradia.terms}
    assert {"apartamento", "fração", "condóminos"} <= set(terms)
    c2 = terms["apartamento"].evidence
    assert c2 and c2[0]["project"] == "R1" and c2[0]["source"] == "CTE"  # case C2
    assert "apartamento" in c2[0]["text"].casefold()
    assert (
        db.scalars(select(Typology).where(Typology.name == "biblioteca")).one().status == "proposed"
    )
    assert all(t.status == "proposed" for t in moradia.terms)


def test_seeding_again_keeps_the_curator_decisions(db: Session, seeded: dict[str, int]) -> None:
    proposal = db.scalars(select(CableEquivalence)).first()
    assert proposal is not None
    proposal.status, proposal.review_note = "rejected", "Não são equivalentes em reação ao fogo."
    db.flush()

    again = seed_knowledge(db, FIXTURES)

    assert again == seeded
    db.refresh(proposal)
    assert (proposal.status, proposal.review_note) == (
        "rejected",
        "Não são equivalentes em reação ao fogo.",
    )
    assert db.scalars(select(CableDesignation).where(CableDesignation.canonical == "XAV")).one()


# ---------------------------------------------------------------- API


def test_everyone_reads_the_dictionary_and_the_lexicon(api: Api, seeded: dict[str, int]) -> None:
    cables_out = api.as_("redator").get("/api/knowledge/cables").json()
    by_name = {d["canonical"]: d for d in cables_out["designations"]}
    assert by_name["H07V-K"]["flexible"] is True and by_name["H07V-U"]["flexible"] is False
    assert by_name["XZ1(frt,zh)"]["occurrences"][0]["raw_text"]
    pair = next(
        e for e in cables_out["equivalences"] if {e["a"], e["b"]} == {"RZ1-K (AS)", "XZ1(frt,zh)"}
    )
    assert pair["status"] == "proposed" and pair["evidence"]
    [moradia] = [t for t in api.as_("tecnico").get("/api/knowledge/typologies").json()
                 if t["name"] == "moradia unifamiliar"]  # fmt: skip
    assert any(t["term"] == "apartamento" and t["evidence"] for t in moradia["terms"])


def test_empty_knowledge_base_answers_empty_lists(api: Api) -> None:
    assert api.as_("redator").get("/api/knowledge/cables").json() == {
        "designations": [], "equivalences": [],
    }  # fmt: skip
    assert api.as_("redator").get("/api/knowledge/typologies").json() == []


@pytest.mark.parametrize("login", ["redator", "tecnico", "admin"])
def test_only_a_curator_decides(api: Api, db: Session, seeded: dict[str, int], login: str) -> None:
    equivalence = db.scalars(select(CableEquivalence)).first()
    assert equivalence is not None
    response = api.as_(login).post(
        f"/api/knowledge/cable-equivalences/{equivalence.id}/review", json={"decision": "approved"}
    )
    assert response.status_code == 403
    assert "Curador" in response.json()["detail"]
    db.refresh(equivalence)
    assert equivalence.status == "proposed"


def test_curator_approves_an_equivalence_and_it_is_audited(
    api: Api, db: Session, seeded: dict[str, int]
) -> None:
    rz1, xz1 = family(db, "RZ1-K (AS)"), family(db, "XZ1(frt,zh)")
    equivalence = db.scalars(
        select(CableEquivalence).where(
            CableEquivalence.a_id == rz1.id, CableEquivalence.b_id == xz1.id
        )
    ).one()

    response = api.as_("curador").post(
        f"/api/knowledge/cable-equivalences/{equivalence.id}/review",
        json={"decision": "approved", "note": "Ambos LSZH para esta secção."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["reviewed_by"] == "dev:curador"
    db.refresh(rz1)
    db.refresh(xz1)
    assert rz1.aliases == ["XZ1(frt,zh)"] and xz1.aliases == ["RZ1-K (AS)"]
    [event] = api.as_("curador").get("/api/activity").json()
    assert event["description"] == "Aprovou a equivalência de cabos «RZ1-K (AS) ≈ XZ1(frt,zh)»"
    assert event["project_id"] is None

    api.as_("curador").post(
        f"/api/knowledge/cable-equivalences/{equivalence.id}/review", json={"decision": "rejected"}
    )
    db.refresh(rz1)
    assert rz1.aliases == []


def test_curator_rejects_a_term(api: Api, db: Session, seeded: dict[str, int]) -> None:
    moradia = db.scalars(select(Typology).where(Typology.name == "moradia unifamiliar")).one()
    term = next(t for t in moradia.terms if t.term == "partes comuns")

    response = api.as_("curador").post(
        f"/api/knowledge/typology-terms/{term.id}/review",
        json={"decision": "rejected", "note": " "},
    )

    assert response.json()["status"] == "rejected" and response.json()["review_note"] is None
    [event] = api.as_("curador").get("/api/activity").json()
    assert (
        event["description"]
        == "Rejeitou o termo incompatível «partes comuns (moradia unifamiliar)»"
    )


def test_review_of_something_unknown(api: Api) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        api.as_("curador")
        .post(f"/api/knowledge/typologies/{missing}/review", json={"decision": "approved"})
        .status_code
        == 404
    )
    assert (
        api.as_("curador")
        .post(f"/api/knowledge/blocks/{missing}/review", json={"decision": "approved"})
        .status_code
        == 422
    )
    assert (
        api.as_("curador")
        .post(f"/api/knowledge/typologies/{missing}/review", json={"decision": "proposed"})
        .status_code
        == 422
    )


def test_the_command_seeds_the_fixtures_and_commits(
    db: Session,
    store: ObjectStore,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """make seed-library runs `python -m app.knowledge.seed` in the backend container."""
    if not (FIXTURES / "R1").is_dir():
        pytest.skip("data/fixtures/R1 é preciso")
    monkeypatch.setenv("FIXTURES_ROOT", str(FIXTURES))

    def factory(url: object) -> Callable[[], AbstractContextManager[Session]]:
        assert isinstance(url, str)  # a database URL, as session_factory expects
        return lambda: nullcontext(db)

    monkeypatch.setattr("app.db.session_factory", factory)
    monkeypatch.setattr("app.storage.get_store", lambda settings: store)

    seed.main()

    assert "Base de conhecimento semeada" in capsys.readouterr().out
    assert db.scalars(select(CableDesignation).where(CableDesignation.canonical == "H07V-U")).one()
    assert db.scalars(select(SourceDocument)).all()  # and the MDJ/CTE split into sections
