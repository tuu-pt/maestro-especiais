"""Approval and revisions of a document (Phase 6, task 1): only the técnico assigned approves,
and only with every condition met; reopening starts the next revision."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import Api
from reference_projects import have_fixtures, load_confirmed, seed_library
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Document, DocumentRevision, Section, TemplateBlock, ValidationRun
from app.storage import ObjectStore

pytestmark = [
    pytest.mark.skipif(not have_fixtures(), reason="sem fixtures de R1"),
    pytest.mark.usefixtures("inline_ingestion"),
]


def approval(api: Api, document_id: str, login: str = "tecnico") -> dict[str, Any]:
    response = api.as_(login).get(f"/api/documents/{document_id}/approval")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


def failing(data: dict[str, Any]) -> set[str]:
    return {c["code"] for c in data["conditions"] if not c["ok"]}


@pytest.fixture
def mdj(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    created = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
    assert created.status_code == 201, created.text
    return {"project_id": project_id, "id": created.json()["id"]}


def make_ready(api: Api, db: Session, doc: dict[str, Any]) -> None:
    """What the curator, the técnico and the validation would have done, straight in the database."""
    db.execute(update(TemplateBlock).values(status="approved"))
    document = db.get(Document, uuid.UUID(doc["id"]))
    assert document is not None
    for s in document.sections:
        s.status = "reviewed"
    db.add(ValidationRun(project_id=document.project_id, status="done",
                         finished_at=datetime.now(UTC)))  # fmt: skip
    db.commit()
    sent = api.as_("tecnico").post(f"/api/projects/{doc['project_id']}/review-request", json={})
    assert sent.status_code == 200, sent.text


def test_the_card_lists_every_condition_with_its_reason(api: Api, mdj: dict[str, Any]) -> None:
    data = approval(api, mdj["id"])

    assert data["status"] == "draft" and data["revision_label"] == "A"
    assert data["responsible_id"] == "dev:tecnico"  # who confirmed the ficha-base, not the redator
    assert failing(data) == {"sections", "blocks", "validation"}
    blocks = next(c for c in data["conditions"] if c["code"] == "blocks")
    assert blocks["link"] == "/conhecimento?separador=blocos"
    assert {i["reason"] for i in blocks["items"]} == {"bloco não aprovado"}
    sections = next(c for c in data["conditions"] if c["code"] == "sections")
    assert sections["link"].startswith(f"/projetos/{mdj['project_id']}/documentos?doc=MDJ&seccao=")
    assert data["can_approve"] is False

    refused = api.as_("tecnico").post(f"/api/documents/{mdj['id']}/approve")
    assert refused.status_code == 409
    assert {c["code"] for c in refused.json()["detail"]["conditions"]} == failing(data)


def test_the_technician_approves_and_reopening_makes_revision_b(
    api: Api, db: Session, mdj: dict[str, Any]
) -> None:
    make_ready(api, db, mdj)
    assert approval(api, mdj["id"])["can_approve"] is True

    approved = api.as_("tecnico").post(f"/api/documents/{mdj['id']}/approve")

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    [revision] = approved.json()["revisions"]
    assert (revision["label"], revision["file_version"], revision["header_revision"]) == (
        "A", "V0", "R00",
    )  # fmt: skip
    section = db.scalars(select(Section).where(Section.document_id == uuid.UUID(mdj["id"]))).first()
    assert section is not None
    edit = api.as_("tecnico").post(f"/api/sections/{section.id}/review", json={})
    assert edit.status_code == 409 and "reabra" in edit.json()["detail"]

    short = api.as_("tecnico").post(f"/api/documents/{mdj['id']}/reopen", json={"reason": "x"})
    assert short.status_code == 422
    reopened = api.as_("tecnico").post(
        f"/api/documents/{mdj['id']}/reopen", json={"reason": "Pedido do dono de obra."}
    )

    assert reopened.status_code == 200, reopened.text
    data = reopened.json()
    assert (data["status"], data["revision_label"], data["file_version"]) == ("draft", "B", "V1")
    assert data["revisions"][0]["reopen_reason"] == "Pedido do dono de obra."
    assert len(db.scalars(select(DocumentRevision)).all()) == 1
    audit = [e["description"] for e in
             api.as_("tecnico").get(f"/api/projects/{mdj['project_id']}/audit").json()]  # fmt: skip
    assert "Aprovou o MDJ (rev. A)" in audit
    assert "Reabriu o MDJ: rev. A → rev. B (Pedido do dono de obra.)" in audit


def test_only_the_assigned_technician_approves(api: Api, db: Session, mdj: dict[str, Any]) -> None:
    make_ready(api, db, mdj)
    db.execute(update(Document).values(responsible_user_id="outro:tecnico"))
    db.commit()

    data = approval(api, mdj["id"])
    refused = api.as_("tecnico").post(f"/api/documents/{mdj['id']}/approve")

    assert data["ready"] is True and data["can_approve"] is False
    assert data["why_not"].startswith("Só o técnico atribuído")
    assert refused.status_code == 409
    assert api.as_("redator").post(f"/api/documents/{mdj['id']}/approve").status_code == 403


def test_assigning_the_responsible(api: Api, mdj: dict[str, Any]) -> None:
    url = f"/api/documents/{mdj['id']}/responsible"
    reason = "Mudança de equipa no projeto."
    not_tecnico = api.as_("admin").patch(url, json={"user_id": "dev:redator", "reason": reason})
    assert not_tecnico.status_code == 422
    assert api.as_("redator").patch(url, json={"user_id": "dev:tecnico", "reason": reason}
                                    ).status_code == 403  # fmt: skip
    ok = api.as_("admin").patch(url, json={"user_id": "dev:tecnico", "reason": reason})
    assert ok.status_code == 200 and ok.json()["responsible_name"].startswith("Técnico")


def test_the_header_date_is_only_what_the_technician_writes(api: Api, mdj: dict[str, Any]) -> None:
    url = f"/api/documents/{mdj['id']}/header"
    assert approval(api, mdj["id"])["header_date"] is None  # P8: empty by default
    assert api.as_("tecnico").patch(url, json={"header_date": "amanhã"}).status_code == 422
    ok = api.as_("tecnico").patch(url, json={"header_date": "junho/2026"})
    assert ok.status_code == 200 and ok.json()["header_date"] == "JUNHO/2026"
    cleared = api.as_("tecnico").patch(url, json={"header_date": None})
    assert cleared.json()["header_date"] is None


def test_a_ficha_revised_after_the_assembly_asks_to_assemble_again(
    api: Api, mdj: dict[str, Any]
) -> None:
    added = api.as_("tecnico").post(
        f"/api/projects/{mdj['project_id']}/ficha/values",
        json={"key": "id.obra.designacao", "value": "Moradia", "note": "Do cliente."},
    )
    revision = api.as_("tecnico").get(f"/api/projects/{mdj['project_id']}/ficha").json()["revision"]
    api.as_("tecnico").post(f"/api/ficha/revisions/{revision['id']}/confirm")

    assert added.status_code == 201
    ficha = next(c for c in approval(api, mdj["id"])["conditions"] if c["code"] == "ficha")
    assert not ficha["ok"] and "volte a montar" in ficha["reason"]
