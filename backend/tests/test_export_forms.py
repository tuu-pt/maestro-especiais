"""Forms of the export (Phase 6, task 4): every part of each package is the template's, byte for
byte, except what was filled; the draft carries its watermark; the FE reads back the ficha-base."""

import io
import uuid
import zipfile

import pytest
from conftest import Api
from reference_projects import have_fixtures, load_confirmed
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.assemble import confirmed_revision
from app.assembly.values import ValueSource
from app.config import Settings
from app.export import WATERMARK
from app.export.checks import check_xlsm, soffice
from app.forms.fill import FORMS, fill, template
from app.ingest.ficha_eletrotecnica import _clean, cell_maps
from app.models import FichaValue
from app.profiles import revision_profile

pytestmark = [
    pytest.mark.skipif(not have_fixtures(), reason="sem fixtures de R1"),
    pytest.mark.usefixtures("inline_ingestion"),
]
SHEET = "xl/worksheets/sheet1.xml"


def parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist()}


@pytest.fixture
def values(api: Api, db: Session, settings: Settings) -> ValueSource:
    project_id = load_confirmed(api, "R1")
    revision = confirmed_revision(db, uuid.UUID(project_id))
    assert revision is not None
    return ValueSource.load(db, revision, revision_profile(db, settings, revision))


def ficha_values(db: Session, values: ValueSource) -> dict[str, object]:
    mapped = set(cell_maps()["FE_v.20190222"].cells.values())
    rows = db.scalars(select(FichaValue).where(FichaValue.revision_id == values.revision_id))
    return {v.key: _clean(v.key, v.value) for v in rows
            if v.key in mapped and v.value not in (None, "", [])}  # fmt: skip


def test_the_fe_changes_only_its_sheet_and_reads_back_the_ficha(
    db: Session, values: ValueSource
) -> None:
    data = fill("ficha_eletrotecnica", values).data
    tpl = template(FORMS["ficha_eletrotecnica"].template)

    report = check_xlsm(data, tpl, sheet=SHEET, reread=ficha_values(db, values))

    assert report.ok, report.problems
    out, before = parts(data), parts(tpl)
    assert out["xl/vbaProject.bin"] == before["xl/vbaProject.bin"]
    assert out["xl/workbook.xml"] == before["xl/workbook.xml"]  # not even re-serialised
    assert [i.date_time for i in zipfile.ZipFile(io.BytesIO(data)).infolist()] == [
        i.date_time for i in zipfile.ZipFile(io.BytesIO(tpl)).infolist()
    ]


def test_the_draft_fe_carries_the_watermark_in_its_sheet_only(values: ValueSource) -> None:
    data = fill("ficha_eletrotecnica", values, WATERMARK).data
    tpl = template(FORMS["ficha_eletrotecnica"].template)

    report = check_xlsm(data, tpl, sheet=SHEET)

    assert report.ok, report.problems
    sheet = parts(data)[SHEET].decode("utf-8")
    assert "<headerFooter" in sheet and WATERMARK in sheet
    # the schema order: the header comes after the page setup and before the drawings
    for later in ("<drawing", "<legacyDrawing", "<extLst"):
        if later in sheet:
            assert sheet.index("<headerFooter") < sheet.index(later), later


@pytest.mark.parametrize("kind", ["identificacao", "termo"])
@pytest.mark.parametrize("draft", [False, True])
def test_identification_and_term_change_only_their_text(
    values: ValueSource, kind: str, draft: bool
) -> None:
    data = fill(kind, values, WATERMARK if draft else None).data
    tpl = template(FORMS[kind].template)
    out, before = parts(data), parts(tpl)

    assert list(out) == list(before)
    changed = {n for n in before if out[n] != before[n]}
    headers = {n for n in before if n.startswith("word/header")}
    assert changed == ({"word/document.xml"} | (headers if draft else set()))
    if draft:
        assert all(WATERMARK in out[n].decode("utf-8") for n in headers)
    text = out["word/document.xml"].decode("utf-8")
    assert "{{" not in text and not any(f"/{y}" in text for y in ("2025", "2026"))  # no date


NO_LIBREOFFICE = "LibreOffice não instalado (corre no contentor e na CI)"


@pytest.mark.skipif(soffice() is None, reason=NO_LIBREOFFICE)
def test_libreoffice_opens_the_fe(values: ValueSource) -> None:
    data = fill("ficha_eletrotecnica", values).data
    report = check_xlsm(data, template(FORMS["ficha_eletrotecnica"].template), sheet=SHEET,
                        libreoffice=True)  # fmt: skip
    assert report.ok and not report.notes, (report.problems, report.notes)
