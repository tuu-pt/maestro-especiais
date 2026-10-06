"""The set of the project (Phase 6, task 5): draft and official .zip with the TUU names and a
manifest, kept in S3 with their hashes, downloads by role, signed links for TUU Maestro (D9)."""

import hashlib
import io
import json
import logging
import uuid
import zipfile
from typing import Any
from urllib.parse import urlparse

import pytest
from approvals import approve_all, assembled_r1
from conftest import Api, Published, RecordingQueue
from fastapi import FastAPI
from reference_projects import have_fixtures
from sqlalchemy.orm import Session

from app.config import Settings
from app.export.bundle import run_export
from app.export.checks import soffice
from app.export.jobs import get_export_queue
from app.models import Export
from app.profiles import DEV_PROFILE
from app.storage import ObjectStore

pytestmark = [
    pytest.mark.skipif(not have_fixtures(), reason="sem fixtures de R1"),
    pytest.mark.usefixtures("inline_ingestion"),
]
SECRET, TOKEN = "segredo-de-teste", "token-de-servico-de-teste"


@pytest.fixture
def exports(app: FastAPI, db: Session, store: ObjectStore, settings: Settings,
            published: Published) -> RecordingQueue:  # fmt: skip
    settings.export_link_secret, settings.maestro_service_token = SECRET, TOKEN
    q = RecordingQueue()
    q.run = lambda export_id: run_export(db, store, settings, published, export_id)
    app.dependency_overrides[get_export_queue] = lambda: q
    return q


@pytest.fixture
def r1(api: Api, db: Session, store: ObjectStore, exports: RecordingQueue) -> dict[str, Any]:
    return assembled_r1(api, db, store)


def ask(api: Api, r1: dict[str, Any], kind: str, login: str = "tecnico") -> Any:
    return api.as_(login).post(f"/api/projects/{r1['project_id']}/exports", json={"kind": kind})


def bundle(api: Api, export_id: str, login: str = "tecnico") -> zipfile.ZipFile:
    response = api.as_(login).get(f"/api/exports/{export_id}/bundle.zip")
    assert response.status_code == 200, response.text
    return zipfile.ZipFile(io.BytesIO(response.content))


def test_the_draft_set_never_takes_the_official_names(api: Api, r1: dict[str, Any]) -> None:
    response = ask(api, r1, "draft", "redator")

    assert response.status_code == 202, response.text
    export = api.as_("redator").get(f"/api/exports/{response.json()['id']}").json()
    assert export["status"] == "done", export["message"]
    assert export["zip_name"] == "R1_Conjunto_RASCUNHO-nao-aprovado.zip"
    names = set(bundle(api, export["id"], "redator").namelist())
    assert names == {
        "R1_MDJ_RASCUNHO-nao-aprovado.docx", "R1_CTE_RASCUNHO-nao-aprovado.docx",
        "R1_FichaEletrotecnica_RASCUNHO-nao-aprovado.xlsm",
        "R1_IdentificacaoProjeto_RASCUNHO-nao-aprovado.docx",
        "R1_TermoResponsabilidade_RASCUNHO-nao-aprovado.docx", "manifesto.json",
    }  # fmt: skip


def test_the_official_set_is_refused_with_its_reasons(api: Api, r1: dict[str, Any]) -> None:
    response = ask(api, r1, "official")

    assert response.status_code == 409
    reasons = response.json()["detail"]["reasons"]
    assert any(r.startswith("MDJ: ") and "por aprovar" in r for r in reasons)
    assert any("aprovado pelo técnico responsável" in r for r in reasons)
    assert ask(api, r1, "official", "redator").status_code == 403


def test_the_official_set_of_r1(
    api: Api, db: Session, store: ObjectStore, r1: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    approve_all(api, db, r1)
    caplog.set_level(logging.DEBUG)

    response = ask(api, r1, "official")

    assert response.status_code == 202, response.text
    export = api.as_("tecnico").get(f"/api/exports/{response.json()['id']}").json()
    assert export["status"] == "done", export["message"]
    assert export["zip_name"] == "R1_PE_ELE_V0.zip"
    z = bundle(api, export["id"])
    assert set(z.namelist()) == {
        "R1_MDJ_PE_ELE_V0.docx", "R1_CTE_PE_ELE_V0.docx", "R1_FichaEletrotecnica_PE_ELE_V0.xlsm",
        "R1_IdentificacaoProjeto_PE_ELE_V0.docx", "R1_TermoResponsabilidade_PE_ELE_V0.docx",
        "manifesto.json",
    }  # fmt: skip
    manifest = json.loads(z.read("manifesto.json"))
    assert manifest["tipo"] == "oficial" and manifest["versao"] == "V0"
    assert manifest["verificacoes"]["problemas"] == []
    assert {p["tipo"]: p["revisao"] for p in manifest["pecas"]} == {"MDJ": "A", "CTE": "A"}
    assert all(p["aprovada_por"].startswith("Técnico") for p in manifest["pecas"])
    termo = next(f for f in manifest["ficheiros"] if f["name"].startswith("R1_Termo"))
    assert "Data e assinatura do técnico responsável" in termo["por_preencher"]
    # every file in S3 with its hash; the keys never hold a file name
    row = db.get(Export, uuid.UUID(export["id"]))
    assert row is not None
    for f in row.files:
        assert hashlib.sha256(store.get(f["key"])).hexdigest() == f["sha256"]
        assert f["name"] not in f["key"]
    # no personal value in the logs while exporting (the files do carry them)
    for value in (DEV_PROFILE["tec.nome"], DEV_PROFILE["tec.nif"], DEV_PROFILE["tec.email"]):
        assert value not in caplog.text
    audit = [e["description"] for e in
             api.as_("tecnico").get(f"/api/projects/{r1['project_id']}/audit").json()]  # fmt: skip
    assert "Conjunto oficial exportado (5 ficheiros, V0)" in audit


def test_downloads_by_role(api: Api, db: Session, r1: dict[str, Any]) -> None:
    draft = ask(api, r1, "draft").json()["id"]
    assert api.as_("curador").get(f"/api/exports/{draft}/bundle.zip").status_code == 403
    assert api.as_("admin").get(f"/api/exports/{draft}/bundle.zip").status_code == 403
    approve_all(api, db, r1)
    official = ask(api, r1, "official").json()["id"]
    assert api.as_("admin").get(f"/api/exports/{official}/bundle.zip").status_code == 200
    assert api.as_("curador").get(f"/api/exports/{official}/bundle.zip").status_code == 403


def test_tuu_maestro_gets_the_manifest_and_signed_links(
    api: Api, db: Session, r1: dict[str, Any]
) -> None:
    approve_all(api, db, r1)
    ask(api, r1, "official")
    url = "/api/integration/projects/R1/export"

    assert api.as_(None).get(url).status_code == 401
    assert api.as_(None).get(url, headers={"X-Service-Token": "errado"}).status_code == 401
    response = api.as_(None).get(url, headers={"X-Service-Token": TOKEN})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["versao"] == "V0" and data["manifesto"]["tipo"] == "oficial"
    link = urlparse(data["conjunto"]["link"])
    signed = api.as_(None).get(f"{link.path}?{link.query}")  # no login: the signature is enough
    assert signed.status_code == 200
    assert hashlib.sha256(signed.content).hexdigest() == data["conjunto"]["sha256"]
    forged = api.as_(None).get(f"{link.path}?{link.query.replace('token=', 'token=0')}")
    assert forged.status_code == 403


NO_LIBREOFFICE = "LibreOffice não instalado (corre no contentor e na CI)"


@pytest.mark.skipif(soffice() is None, reason=NO_LIBREOFFICE)
def test_the_set_can_carry_a_pdf_of_each_piece(api: Api, db: Session, r1: dict[str, Any]) -> None:
    approve_all(api, db, r1)
    response = api.as_("tecnico").post(f"/api/projects/{r1['project_id']}/exports",
                                       json={"kind": "official", "pdf": True})  # fmt: skip
    export = api.as_("tecnico").get(f"/api/exports/{response.json()['id']}").json()
    assert export["status"] == "done", export["message"]
    names = bundle(api, export["id"]).namelist()
    assert {"R1_MDJ_PE_ELE_V0.pdf", "R1_CTE_PE_ELE_V0.pdf"} <= set(names)
