from typing import Any

import factories
import pytest
from conftest import Api
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.detect import detect
from app.models import AuditEvent
from app.storage import ObjectStore


def create(api: Api, code: str = "R9", login: str = "redator") -> dict[str, Any]:
    response = api.as_(login).post("/api/projects", json={"code": code, "name": "Moradia"})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def upload(api: Api, project_id: str, name: str, data: bytes, login: str = "redator") -> Any:
    return api.as_(login).post(f"/api/projects/{project_id}/files", files={"file": (name, data)})


# ---------------------------------------------------------------- projects


def test_new_database_has_no_projects(api: Api) -> None:
    assert api.as_("redator").get("/api/projects").json() == []


def test_create_and_list_project(api: Api, db: Session) -> None:
    created = create(api)

    listed = api.as_("curador").get("/api/projects").json()
    assert [p["code"] for p in listed] == ["R9"]
    assert listed[0]["file_count"] == 0 and listed[0]["ficha_status"] is None
    assert created["created_by"] == "dev:redator"
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "project.created")).one()
    assert event.actor_id == "dev:redator" and event.payload == {"code": "R9"}


@pytest.mark.parametrize(
    ("login", "expected"), [("curador", 403), ("admin", 403), ("tecnico", 201)]
)
def test_only_redator_and_tecnico_create_projects(api: Api, login: str, expected: int) -> None:
    response = api.as_(login).post("/api/projects", json={"code": "R9", "name": "x"})
    assert response.status_code == expected


def test_duplicate_code_is_409(api: Api) -> None:
    create(api)
    response = api.as_("redator").post("/api/projects", json={"code": "R9", "name": "x"})
    assert response.status_code == 409


@pytest.mark.parametrize("code", ["r9", "R", "R 9", "../R9"])
def test_invalid_codes_are_rejected(api: Api, code: str) -> None:
    response = api.as_("redator").post("/api/projects", json={"code": code, "name": "x"})
    assert response.status_code == 422


def test_unknown_project_is_404(api: Api) -> None:
    assert (
        api.as_("redator").get(f"/api/projects/{'0' * 8}-0000-0000-0000-{'0' * 12}").status_code
        == 404
    )


# ---------------------------------------------------------------- uploads


def test_upload_stores_file_with_checksum_and_detected_kind(
    api: Api, store: ObjectStore, db: Session
) -> None:
    project = create(api)
    data = factories.ficha_eletrotecnica()

    response = upload(api, project["id"], "Ficha do Sr. Fulano.xlsm", data)

    assert response.status_code == 202, response.text  # queued for reading
    file = response.json()["file"]
    assert file["kind"] == "ficha_eletrotecnica"
    assert file["template_version"] == factories.FE_VERSION
    assert file["ingest_status"] == "pending"
    import hashlib

    assert file["checksum"] == hashlib.sha256(data).hexdigest()
    key = f"projects/{project['id']}/files/{file['id']}"
    assert store.get(key) == data
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "file.uploaded")).one()
    assert "Fulano" not in str(event.payload)  # the original name never reaches the audit log
    assert event.payload["kind"] == "ficha_eletrotecnica"


def test_storage_key_never_contains_the_original_name(
    api: Api, store: ObjectStore, db: Session
) -> None:
    project = create(api)
    upload(api, project["id"], "Termo Maria.docx", b"PK\x03\x04docx")
    from app.models import ProjectFile

    stored = db.scalars(select(ProjectFile)).one()
    assert "Maria" not in stored.storage_key and stored.filename == "Termo Maria.docx"


def test_same_file_twice_returns_the_existing_one(api: Api, store: ObjectStore) -> None:
    project = create(api)
    data = factories.tabela_calculo()
    first = upload(api, project["id"], "Tabela.xlsx", data).json()
    second = upload(api, project["id"], "Tabela (cópia).xlsx", data)

    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["file"]["id"] == first["file"]["id"]
    assert len(api.as_("redator").get(f"/api/projects/{project['id']}/files").json()) == 1


def test_curador_cannot_upload(api: Api, store: ObjectStore) -> None:
    project = create(api)
    assert (
        upload(api, project["id"], "a.pdf", factories.PDF_MINIMAL, login="curador").status_code
        == 403
    )


def test_empty_and_too_large_files_are_rejected(api: Api, store: ObjectStore, app: FastAPI) -> None:
    project = create(api)
    assert upload(api, project["id"], "vazio.pdf", b"").status_code == 422
    from app.config import get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(dev_auth=True, max_upload_bytes=10)
    assert upload(api, project["id"], "grande.pdf", b"%PDF-" + b"x" * 20).status_code == 413


def test_files_without_a_reader_yet_are_stored_and_skipped(api: Api, store: ObjectStore) -> None:
    project = create(api)
    file = upload(api, project["id"], "Desenhos.pdf", factories.PDF_MINIMAL).json()["file"]

    assert file["kind"] == "drawing_pdf"
    assert file["ingest_status"] == "skipped"
    assert "Fase 2" in file["ingest_message"]


# ---------------------------------------------------------------- detection


@pytest.mark.parametrize(
    ("name", "data", "kind"),
    [
        ("FE.xlsm", factories.ficha_eletrotecnica(), "ficha_eletrotecnica"),
        ("qualquer nome.xlsx", factories.tabela_calculo(), "calc_summary"),
        ("MQT.xlsx", factories.mqt(), "mqt"),
        ("pecas.pdf", factories.PDF_MINIMAL, "drawing_pdf"),
        ("EL001.dwg", b"AC1032", "drawing_dwg"),
        ("MDJ.docx", b"PK", "other"),
    ],
)
def test_kind_is_detected_from_content(name: str, data: bytes, kind: str) -> None:
    assert detect(name, data).kind == kind


def test_tabela_is_found_by_header_text_not_position() -> None:
    header = ["", "Destino", "Origem", *factories.CALC_HEADER[2:]]
    assert detect("t.xlsx", factories.tabela_calculo(header=header)).kind == "calc_summary"


def test_corrupted_workbook_is_other_with_a_note() -> None:
    found = detect("FE.xlsm", b"PK\x03\x04 not really a zip")
    assert found.kind == "other" and found.note == "Ficheiro ilegível ou corrompido."


def test_old_calc_sheet_with_the_four_sheets_is_calc_circuit() -> None:
    xlwt = pytest.importorskip("xlwt")
    import io

    wb = xlwt.Workbook()
    for name in ("IB", "condutores", "tensao", "proteccao"):
        wb.add_sheet(name).write(0, 0, 1)
    buffer = io.BytesIO()
    wb.save(buffer)
    assert detect("09-Folha.xls", buffer.getvalue()).kind == "calc_circuit"
