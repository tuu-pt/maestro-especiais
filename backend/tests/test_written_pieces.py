"""Written pieces made by hand, uploaded to audit a project (Phase 5, task 2)."""

from pathlib import Path
from typing import Any

import pytest
from conftest import Api, Published, RecordingQueue
from reference_projects import FIXTURES, have_fixtures, load_confirmed
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.detect import detect
from app.knowledge.sources import unique_files
from app.models import Document, FichaValue, PieceFacts
from app.storage import ObjectStore
from app.validation.engine import run_validation

pytestmark = [
    pytest.mark.usefixtures("inline_ingestion"),
    pytest.mark.skipif(not have_fixtures(), reason="data/fixtures/R1 e R2 são precisos"),
]


def written(code: str, kind: str) -> Path:
    return next(p for p in unique_files(FIXTURES / code)
                if p.suffix == ".docx" and detect(p.name, p.read_bytes()).kind == kind)  # fmt: skip


def upload(api: Api, project_id: str, path: Path) -> dict[str, Any]:
    response = api.as_("redator").post(
        f"/api/projects/{project_id}/files", files={"file": (path.name, path.read_bytes())}
    )
    assert response.status_code == 202, response.text
    files = api.as_("redator").get(f"/api/projects/{project_id}/files").json()
    return next(f for f in files if f["filename"] == path.name)


def texts(content: dict[str, Any]) -> str:
    out = []

    def walk(node: dict[str, Any]) -> None:
        if node.get("type") == "text":
            out.append(node.get("text", ""))
        for child in node.get("content") or []:
            walk(child)

    walk(content)
    return "\n".join(out)


@pytest.mark.parametrize(
    ("code", "kind"),
    [("R1", "mdj_docx"), ("R1", "cte_docx"), ("R1", "identificacao_docx"), ("R1", "termo_docx"),
     ("R2", "mdj_docx"), ("R2", "cte_docx")],
)  # fmt: skip
def test_written_pieces_are_found_by_their_title(code: str, kind: str) -> None:
    assert written(code, kind).suffix == ".docx"


def test_a_word_document_without_a_known_title_is_kept_as_other() -> None:
    import io

    import docx

    document = docx.Document()
    document.add_paragraph("Ata da reunião de obra")
    buffer = io.BytesIO()
    document.save(buffer)

    found = detect("ata.docx", buffer.getvalue())

    assert found.kind == "other" and found.note is not None


def test_an_existing_mdj_becomes_a_read_only_document_with_masked_personal_values(
    api: Api, db: Session
) -> None:
    project_id = load_confirmed(api, "R1")

    file = upload(api, project_id, written("R1", "mdj_docx"))

    assert file["kind"] == "mdj_docx" and file["ingest_status"] == "done"
    assert "MDJ existente" in file["ingest_message"]
    docs = api.as_("redator").get(f"/api/projects/{project_id}/documents").json()
    existing = next(d for d in docs if d["origin"] == "existing")
    assert existing["type"] == "MDJ" and existing["source_file_id"] == file["id"]
    full = api.as_("redator").get(f"/api/documents/{existing['id']}").json()
    kinds = [s["kind"] for s in full["sections"]]
    assert kinds[0] == "cover" and "signature" in kinds and kinds.count("block") > 10
    shown = "\n".join(texts(s["content"]) for s in full["sections"])
    personal = db.scalars(select(FichaValue.value).where(FichaValue.personal_data.is_(True))).all()
    names = [v for v in personal if isinstance(v, str) and len(v) > 6]
    assert names and not [n for n in names if n.lower() in shown.lower()]  # masked, never shown
    assert "•••" in shown


def test_an_existing_piece_cannot_be_edited_and_a_new_upload_replaces_it(
    api: Api, db: Session
) -> None:
    project_id = load_confirmed(api, "R2", resolve=True)
    upload(api, project_id, written("R2", "cte_docx"))
    doc = next(d for d in api.as_("redator").get(f"/api/projects/{project_id}/documents").json()
               if d["origin"] == "existing")  # fmt: skip
    section = api.as_("redator").get(f"/api/documents/{doc['id']}").json()["sections"][3]

    edit = api.as_("redator").put(f"/api/sections/{section['id']}/content",
                                  json={"content": section["content"]})  # fmt: skip
    unlock = api.as_("redator").post(f"/api/sections/{section['id']}/unlock",
                                     json={"reason": "Corrigir o texto."})  # fmt: skip

    assert edit.status_code == 409 and "só leitura" in edit.json()["detail"]
    assert unlock.status_code == 409
    count = db.scalars(select(Document).where(
        Document.project_id == project_id, Document.origin == "existing")).all()  # fmt: skip
    assert len(count) == 1


def test_the_validation_reads_the_existing_piece_from_its_original_file(
    api: Api, db: Session, store: ObjectStore, settings: Settings, published: Published,
    validation_queue: RecordingQueue,
) -> None:  # fmt: skip
    validation_queue.run = lambda run_id: None
    project_id = load_confirmed(api, "R1")
    upload(api, project_id, written("R1", "mdj_docx"))
    api.as_("redator").post(f"/api/projects/{project_id}/validation", json={})

    run = run_validation(db, store, settings, published, validation_queue.enqueued[-1])

    assert run is not None and run.status == "done"
    assert [p["origin"] for p in run.pieces if p["kind"] == "MDJ"] == ["existing"]
    cached = db.scalars(select(PieceFacts).where(PieceFacts.project_id == project_id)).all()
    paragraphs = [p for c in cached for p in c.data["paragraphs"]]
    assert any("H07V-K" in p["text"] for p in paragraphs)  # C1 is there to be compared
