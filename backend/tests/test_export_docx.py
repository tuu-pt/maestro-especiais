"""Export of the MDJ and the CTE as .docx (Phase 6, task 3): the draft with its watermark and the
official version, both through every automatic fidelity check."""

import io
import logging
import uuid
import zipfile
from typing import Any

import docx
import pytest
from approvals import approve_all, assembled_r1
from conftest import Api
from reference_projects import have_fixtures
from sqlalchemy.orm import Session

from app.config import Settings
from app.export import WATERMARK, ExportRefused
from app.export.checks import check_docx, soffice
from app.export.docx import expected_counts, export_docx
from app.models import Document
from app.profiles import DEV_PROFILE
from app.storage import ObjectStore

pytestmark = [
    pytest.mark.skipif(not have_fixtures(), reason="sem fixtures de R1"),
    pytest.mark.usefixtures("inline_ingestion"),
]


@pytest.fixture
def r1(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    return assembled_r1(api, db, store)


def document(db: Session, r1: dict[str, Any], doc_type: str) -> Document:
    found = db.get(Document, uuid.UUID(r1["documents"][doc_type]))
    assert found is not None
    return found


def headers(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return "".join(z.read(n).decode("utf-8") for n in z.namelist()
                       if n.startswith("word/header"))  # fmt: skip


@pytest.mark.parametrize("doc_type", ["MDJ", "CTE"])
def test_the_draft_carries_its_watermark_and_never_the_official_name(
    db: Session, store: ObjectStore, settings: Settings, r1: dict[str, Any], doc_type: str
) -> None:
    doc = document(db, r1, doc_type)

    exported = export_docx(db, store, settings, doc, official=False)

    assert exported.name == f"R1_{doc_type}_RASCUNHO-nao-aprovado.docx"
    report = check_docx(exported.data, expected=expected_counts(db, doc), official=False,
                        watermark=WATERMARK, libreoffice=False)  # fmt: skip
    assert report.ok, report.problems
    assert WATERMARK in headers(exported.data)


def test_the_official_export_is_refused_before_the_approval(
    db: Session, store: ObjectStore, settings: Settings, r1: dict[str, Any]
) -> None:
    with pytest.raises(ExportRefused) as refused:
        export_docx(db, store, settings, document(db, r1, "MDJ"), official=True)
    assert "A peça ainda não foi aprovada pelo técnico responsável." in refused.value.reasons
    assert any("por aprovar" in r for r in refused.value.reasons)  # the blocks


@pytest.mark.parametrize("doc_type", ["MDJ", "CTE"])
def test_the_official_export_of_r1_passes_every_check(
    api: Api, db: Session, store: ObjectStore, settings: Settings, r1: dict[str, Any],
    doc_type: str, caplog: pytest.LogCaptureFixture,
) -> None:  # fmt: skip
    approve_all(api, db, r1)
    doc = document(db, r1, doc_type)
    caplog.set_level(logging.DEBUG)

    exported = export_docx(db, store, settings, doc, official=True)

    assert exported.name == f"R1_{doc_type}_PE_ELE_V0.docx"
    report = check_docx(exported.data, expected=expected_counts(db, doc), official=True,
                        libreoffice=False)  # fmt: skip
    assert report.ok, report.problems
    head = headers(exported.data)
    assert "R00" in head and DEV_PROFILE["tec.nome"].upper() in head.upper()
    assert "RASCUNHO" not in head
    assert "JUNHO" not in head.upper()  # P8: the date of R1 is gone, none written by the técnico
    core = zipfile.ZipFile(io.BytesIO(exported.data)).read("docProps/core.xml").decode("utf-8")
    assert "TUU – Building Design Management, Lda" in core and "R1 · " in core  # noqa: RUF001
    text = "\n".join(p.text for p in docx.Document(io.BytesIO(exported.data)).paragraphs)
    assert "Imagens meramente ilustrativas" in text or doc_type == "MDJ"
    assert DEV_PROFILE["tec.nif"] not in caplog.text and DEV_PROFILE["tec.nome"] not in caplog.text


def test_the_date_of_the_header_is_the_one_the_technician_wrote(
    api: Api, db: Session, store: ObjectStore, settings: Settings, r1: dict[str, Any]
) -> None:
    api.as_("tecnico").patch(f"/api/documents/{r1['documents']['MDJ']}/header",
                             json={"header_date": "outubro/2026"})  # fmt: skip
    approve_all(api, db, r1)

    exported = export_docx(db, store, settings, document(db, r1, "MDJ"), official=True)

    assert "OUTUBRO/2026" in headers(exported.data)


NO_LIBREOFFICE = "LibreOffice não instalado (corre no contentor e na CI)"


@pytest.mark.skipif(soffice() is None, reason=NO_LIBREOFFICE)
def test_libreoffice_converts_the_official_mdj(
    api: Api, db: Session, store: ObjectStore, settings: Settings, r1: dict[str, Any]
) -> None:
    approve_all(api, db, r1)
    exported = export_docx(db, store, settings, document(db, r1, "MDJ"), official=True)
    report = check_docx(exported.data, official=True, libreoffice=True)
    assert report.ok and not report.notes, (report.problems, report.notes)
