"""«Aprovar todas as propostas»: one decision of the curator for every proposed block."""

from typing import Any

import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Requirement, TemplateBlock

REASON = "Piloto: propostas dadas como boas (D7 provisório)."


def block(db: Session, key: str, doc_type: str, status: str = "proposed",
          rule: str | None = "true") -> TemplateBlock:  # fmt: skip
    b = TemplateBlock(key=key, doc_type=doc_type, kind="block", level=1, title=key.split(".")[-1],
                      order=1, mode="fixed", activation_rule=rule, status=status)  # fmt: skip
    db.add(b)
    db.flush()
    return b


@pytest.fixture
def library(db: Session) -> dict[str, TemplateBlock]:
    found = {
        "intro": block(db, "ele.mdj.introducao", "MDJ"),
        "bad": block(db, "ele.mdj.regra_partida", "MDJ", rule="ele.classificacao =="),
        "gone": block(db, "ele.mdj.rejeitado", "MDJ", status="rejected"),
        "entry": block(db, "ele.cte.entrada_de_energia", "CTE"),
    }
    db.add(Requirement(block_key="ele.cte.entrada_de_energia", category="portinhola",
                       param_name="ip_rating", operator=">=class", value="IP55"))  # fmt: skip
    db.flush()
    return found


def approve_all(api: Api, login: str = "curador", **body: Any) -> Any:
    return api.as_(login).post("/api/library/blocks/approve-all", json={"reason": REASON, **body})


@pytest.mark.parametrize("login", ["redator", "tecnico", "admin"])
def test_only_a_curator_approves_everything(api: Api, library: dict[str, Any], login: str) -> None:
    assert approve_all(api, login).status_code == 403


def test_a_reason_of_ten_characters_is_needed(api: Api, library: dict[str, Any]) -> None:
    assert approve_all(api, reason="porque sim").status_code == 200  # 10
    assert approve_all(api, reason="curta").status_code == 422


def test_every_proposed_block_is_approved_with_its_requirements_and_audited(
    api: Api, db: Session, library: dict[str, TemplateBlock]
) -> None:
    body = approve_all(api).json()

    assert body["approved"] == 2 and body["requirements_approved"] == 1
    assert [s["key"] for s in body["skipped"]] == ["ele.mdj.regra_partida"]
    assert "Regra de ativação inválida" in body["skipped"][0]["why"]
    statuses = {k: b.status for k, b in library.items()}
    assert statuses == {"intro": "approved", "bad": "proposed", "gone": "rejected",
                        "entry": "approved"}  # fmt: skip
    assert library["intro"].reviewed_by == "dev:curador"
    assert library["intro"].review_note == REASON
    assert db.scalars(select(Requirement)).one().status == "approved"
    events = db.scalars(select(AuditEvent).where(AuditEvent.action.like("library.block%"))).all()
    per_block = [e for e in events if e.action == "library.block_approved"]
    assert len(per_block) == 2 and all(e.payload["all"] for e in per_block)
    summary = next(e for e in events if e.action == "library.blocks_approved_all")
    assert summary.payload == {"doc_type": None, "approved": 2, "skipped": 1,
                               "requirements_approved": 1, "reason": REASON}  # fmt: skip


def test_one_document_only(api: Api, library: dict[str, TemplateBlock]) -> None:
    assert approve_all(api, doc_type="CTE").json()["approved"] == 1
    assert library["intro"].status == "proposed" and library["entry"].status == "approved"


def test_the_activity_says_what_was_approved_and_why(
    api: Api, library: dict[str, TemplateBlock]
) -> None:
    approve_all(api, doc_type="MDJ")

    activity = api.as_("redator").get("/api/activity").json()

    said = [a["description"] for a in activity]
    assert f"Aprovou todas as propostas (1 bloco, MDJ): {REASON}" in said
    assert "Aprovou o bloco «introducao» (MDJ)" in said
