"""The index of an assembled document written from its own titles; page numbers by LibreOffice."""

import io
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from app.assembly import toc
from app.export.checks import soffice
from app.export.toc import paginate
from app.library.docx_blocks import DOCUMENT, STYLES, w
from app.library.sources import reference_documents

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
# The page of each title of R1's MDJ in the PDF that Word made of it (MBERAL_MDJ_PE_ELE_v0.pdf);
# the index cached in the .docx is older (INTRODUÇÃO on 2).
WORD_PDF_PAGES = [3, 3, 4, 5, 5, 5, 5, 5, 6, 6, 6, 7, 7, 8, 8, 8, 8, 9, 9, 10, 10, 10, 10, 10,
                  11, 11, 11, 11, 11, 12, 13]  # fmt: skip
pytestmark = pytest.mark.skipif(not (FIXTURES / "R1").is_dir(), reason="sem fixtures de R1")


def _package(code: str, doc_type: str) -> bytes:
    return next(d for t, _, d in reference_documents(FIXTURES, code) if t == doc_type)


def _parts(data: bytes) -> tuple[bytes, bytes, bytes]:
    z = zipfile.ZipFile(io.BytesIO(data))
    return z.read(DOCUMENT), z.read(STYLES), z.read("word/numbering.xml")


def entries(document_xml: bytes) -> list[tuple[str, str]]:
    """(anchor, "number | title | page") of each index entry."""
    root = etree.fromstring(document_xml)
    out = []
    for link in root.iter(w("hyperlink")):
        anchor = link.get(w("anchor")) or ""
        if anchor.startswith("_Toc"):
            out.append((anchor, " | ".join(t.text or "" for t in link.iter(w("t")))))
    return out


def _without_pages(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(a, re.sub(r" \| \d*$", "", t).replace("\xa0", " ").strip()) for a, t in items]


@pytest.mark.parametrize("code,doc_type", [("R1", "MDJ"), ("R1", "CTE"), ("R2", "MDJ")])
def test_the_rebuilt_index_of_a_reference_document_is_its_own(code: str, doc_type: str) -> None:
    document_xml, styles, numbering = _parts(_package(code, doc_type))

    rebuilt = toc.rebuild(document_xml, styles, numbering)

    assert _without_pages(entries(rebuilt)) == _without_pages(entries(document_xml))
    assert all(t.endswith("| ") for _, t in entries(rebuilt))  # page numbers: not yet
    etree.fromstring(rebuilt)


def _headings(root: Any, text: str) -> Any:
    return next(
        p for p in root.iter(w("p")) if "".join(t.text or "" for t in p.iter(w("t"))) == text
    )


def test_left_out_renamed_and_new_titles_follow_the_document() -> None:
    document_xml, styles, numbering = _parts(_package("R1", "MDJ"))
    root = etree.fromstring(document_xml)
    caixas = _headings(root, "CAIXAS")
    caixas.getparent().remove(caixas)  # a section left out
    for t in _headings(root, "Contagem").iter(w("t")):
        t.text = "Contagem de energia" if t.text == "Contagem" else t.text
    new = etree.fromstring(etree.tostring(_headings(root, "Contagem de energia")))
    for mark in new.findall(w("bookmarkStart")) + new.findall(w("bookmarkEnd")):
        new.remove(mark)
    for t in new.iter(w("t")):
        t.text = "Posto de carregamento"  # a title written by hand: no bookmark
    _headings(root, "Distribuição de Energia").addnext(new)

    rebuilt = etree.fromstring(toc.rebuild(etree.tostring(root), styles, numbering))
    shown = [t for _, t in _without_pages(entries(etree.tostring(rebuilt)))]

    assert "9. | CAIXAS" not in shown and "8. | CANALIZAÇÕES" in shown
    assert "9. | INSTALAÇÕES ELÉTRICAS A CONSIDERAR" in shown  # numbered again
    assert "5.2. | Contagem de energia" in shown
    assert "5.4. | Posto de carregamento" in shown
    anchor = next(a for a, t in entries(etree.tostring(rebuilt)) if "Posto de" in t)
    assert anchor.startswith(toc.TOC_BOOKMARK)
    marks = [el.get(w("name")) for el in rebuilt.iter(w("bookmarkStart"))]
    assert marks.count(anchor) == 1
    ids = [el.get(w("id")) for el in rebuilt.iter(w("bookmarkStart"))]
    assert len(ids) == len(set(ids))


def test_a_document_without_index_is_left_as_it_is() -> None:
    xml = (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body><w:p><w:r><w:t>Sem \xc3\xadndice</w:t></w:r></w:p></w:body></w:document>"
    )
    assert toc.rebuild(xml, None, None) == xml


def test_without_libreoffice_the_document_keeps_updating_its_fields(monkeypatch: Any) -> None:
    monkeypatch.setattr("app.export.checks.soffice", lambda: None)
    assert paginate(_package("R1", "MDJ")) is None


@pytest.mark.skipif(soffice() is None, reason="LibreOffice não instalado (corre no contentor)")
def test_libreoffice_writes_the_page_numbers_and_word_no_longer_asks() -> None:
    data = _package("R1", "MDJ")
    document_xml, styles, numbering = _parts(data)
    rebuilt = toc.rebuild(document_xml, styles, numbering)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, rebuilt if info.filename == DOCUMENT else src.read(info))
    paged = paginate(out.getvalue())

    assert paged is not None
    z = zipfile.ZipFile(io.BytesIO(paged))
    assert b"updateFields" not in z.read("word/settings.xml")
    pages = [int(t.rsplit("| ", 1)[1]) for _, t in entries(z.read(DOCUMENT))]
    differ = [
        (n, a, b) for n, (a, b) in enumerate(zip(pages, WORD_PDF_PAGES, strict=True)) if a != b
    ]
    assert len(differ) <= 1 and all(abs(a - b) == 1 for _, a, b in differ), differ
    assert "§" not in z.read(DOCUMENT).decode()
