"""Page numbers of the index from a LibreOffice PDF, so Word does not ask to update the fields.

app.assembly.toc writes the index entries from the document's titles, without page numbers, and
the draft keeps `updateFields` (Word fills them when the file is opened). Here, when LibreOffice
is installed (the backend image), a copy of the document with a short mark before each title
(`§n§`) is turned into a PDF; the page of each mark is the title's page. The entries get those
numbers and `updateFields` leaves the settings. Without LibreOffice, or when a mark is not found,
the document stays as it was (Word updates the index) [A CONFIRMAR: LibreOffice paginates like
Word in the TUU documents, checked by hand in docs/fase6-verificacao-manual.md].
"""

import io
import re
import zipfile
from typing import Any

from lxml import etree

from app.assembly.toc import set_page
from app.export.checks import to_pdf
from app.library.docx_blocks import DOCUMENT, w

SETTINGS = "word/settings.xml"
_MARK = re.compile(r"§(\d+)§")


def _toc_links(root: Any) -> list[Any]:
    """The hyperlinks of the index entries: those with a PAGEREF to their own anchor."""
    out = []
    for link in root.iter(w("hyperlink")):
        instr = "".join(t.text or "" for t in link.iter(w("instrText")))
        if link.get(w("anchor")) and "PAGEREF" in instr:
            out.append(link)
    return out


def _replace(data: bytes, parts: dict[str, bytes]) -> bytes:
    """The package with some parts replaced; the rest copied as they were, in the same order."""
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as src,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for info in src.infolist():
            dst.writestr(info, parts.get(info.filename, src.read(info.filename)))
    return out.getvalue()


def _marked(root: Any, anchors: list[str]) -> bytes:
    """A copy of the document with §n§ at the start of the n-th title."""
    marked = etree.fromstring(etree.tostring(root))
    starts = {el.get(w("name")): el for el in marked.iter(w("bookmarkStart"))}
    for n, anchor in enumerate(anchors):
        start = starts.get(anchor)
        if start is None:
            continue
        run = etree.Element(w("r"))
        etree.SubElement(run, w("t")).text = f"§{n}§"
        start.addnext(run)
    return etree.tostring(marked, xml_declaration=True, encoding="UTF-8", standalone=True)


def pages_of_marks(pdf: bytes) -> dict[int, int]:
    """Mark n → page (1-based). A mark seen on more than one page (an index updated by the
    converter) is the title on the last of them."""
    import pypdfium2 as pdfium

    found: dict[int, int] = {}
    document = pdfium.PdfDocument(pdf)
    try:
        for i in range(len(document)):
            page = document[i]
            text = page.get_textpage().get_text_range()
            for m in _MARK.finditer(text):
                found[int(m.group(1))] = i + 1
    finally:
        document.close()
    return found


def paginate(data: bytes, *, timeout_s: int = 180) -> bytes | None:
    """The .docx with the page numbers of its index written and no `updateFields`; None when
    they could not be found (no LibreOffice, no index, a title not found)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = etree.fromstring(z.read(DOCUMENT))
        settings = z.read(SETTINGS) if SETTINGS in z.namelist() else None
    links = _toc_links(root)
    if not links:
        return None
    anchors = [link.get(w("anchor")) for link in links]
    pdf, problem = to_pdf(
        _replace(data, {DOCUMENT: _marked(root, anchors)}), "docx", timeout_s=timeout_s
    )
    if pdf is None or problem:
        return None
    pages = pages_of_marks(pdf)
    if any(n not in pages for n in range(len(anchors))):
        return None
    for n, link in enumerate(links):
        set_page(link, str(pages[n]))
    parts = {
        DOCUMENT: etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    }
    if settings is not None:
        s = etree.fromstring(settings)
        for el in s.findall(w("updateFields")):
            s.remove(el)
        parts[SETTINGS] = etree.tostring(s, xml_declaration=True, encoding="UTF-8", standalone=True)
    return _replace(data, parts)
