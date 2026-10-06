"""R1 assembled and approved in the test database (Phase 6): what the curator, the técnico and the
validation would have done, so that the official export can be tested."""

import uuid
from datetime import UTC, datetime
from typing import Any

from conftest import Api
from reference_projects import load_confirmed, seed_library
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Document, TemplateBlock, ValidationRun
from app.storage import ObjectStore


def assembled_r1(api: Api, db: Session, store: ObjectStore,
                 types: tuple[str, ...] = ("MDJ", "CTE")) -> dict[str, Any]:  # fmt: skip
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    # what no source of R1 gives, written by the técnico (task 1a), so the cover can be reviewed
    for key, value in (("id.obra.designacao", "Moradia unifamiliar"), ("id.local.cp", "3000-000")):
        body = {"key": key, "value": value, "note": "Do cliente."}
        added = api.as_("tecnico").post(f"/api/projects/{project_id}/ficha/values", json=body)
        assert added.status_code == 201, added.text
    revision = api.as_("tecnico").get(f"/api/projects/{project_id}/ficha").json()["revision"]
    confirmed = api.as_("tecnico").post(f"/api/ficha/revisions/{revision['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    documents = {}
    for doc_type in types:
        created = api.as_("redator").post(f"/api/projects/{project_id}/documents",
                                          json={"type": doc_type})  # fmt: skip
        assert created.status_code == 201, created.text
        documents[doc_type] = created.json()["id"]
    return {"project_id": project_id, "documents": documents}


def approve_all(api: Api, db: Session, r1: dict[str, Any]) -> None:
    """Blocks approved by the curator, sections reviewed, a validation without criticals, the
    review requested and every document approved by the técnico responsável."""
    db.execute(update(TemplateBlock).values(status="approved"))
    for document_id in r1["documents"].values():
        document = db.get(Document, uuid.UUID(document_id))
        assert document is not None
        for s in document.sections:
            s.status = "reviewed"
    db.add(ValidationRun(project_id=uuid.UUID(r1["project_id"]), status="done",
                         finished_at=datetime.now(UTC)))  # fmt: skip
    db.commit()
    sent = api.as_("tecnico").post(f"/api/projects/{r1['project_id']}/review-request", json={})
    assert sent.status_code == 200, sent.text
    for document_id in r1["documents"].values():
        approved = api.as_("tecnico").post(f"/api/documents/{document_id}/approve")
        assert approved.status_code == 200, approved.text
