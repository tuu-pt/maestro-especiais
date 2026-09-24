"""PDF anonymization with PyMuPDF (AGPL-3.0: tools/ only, never the backend).

Text is truly removed (redaction) and the pseudonym written in its place. Metadata,
XMP, annotations, digital signatures, attachments and JPEG metadata are removed; form
fields, links and bookmarks are anonymized. Text drawn as vectors (AutoCAD SHX fonts)
cannot be read: such pages are flagged for visual review.
"""

from pathlib import Path
from typing import Any

import pymupdf

from anonymizer import images
from anonymizer.engine import Seed, TextAnonymizer
from anonymizer.findings import Finding, UnreadableFileError

EXTENSIONS = (".pdf",)
_VECTOR_DRAWINGS = 1500  # many drawn segments and…
_FEW_CHARS = 200  # …almost no text: probably vectorized lettering
_FONT = "helv"


def _open(path: Path) -> Any:
    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:
        raise UnreadableFileError("unreadable") from exc
    if doc.needs_pass or doc.is_encrypted:
        doc.close()
        raise UnreadableFileError("encrypted")
    if doc.page_count == 0:
        doc.close()
        raise UnreadableFileError("unreadable")
    return doc


def _lines(page: Any) -> list[list[tuple[str, Any, float]]]:
    """Text lines as lists of (char, bbox, font size)."""
    lines = []
    raw = page.get_text("rawdict")
    for block in raw["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            chars = [
                (ch["c"], pymupdf.Rect(ch["bbox"]), span["size"])
                for span in line["spans"]
                for ch in span["chars"]
            ]
            if chars:
                lines.append(chars)
    return lines


def _document_texts(doc: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for key, value in (doc.metadata or {}).items():
        if value:
            out.append((f"metadados · {key}", str(value)))
    xmp = doc.get_xml_metadata()
    if xmp:
        out.append(("metadados XMP", xmp))
    for level, title, *_ in doc.get_toc():
        out.append((f"marcador nível {level}", title))
    out += [(f"anexo {name}", name) for name in doc.embfile_names()]
    for pno, page in enumerate(doc, 1):
        where = f"pág. {pno}"
        out += [(where, "".join(c for c, _, _ in line)) for line in _lines(page)]
        for annot in page.annots() or []:
            info = annot.info
            out += [
                (f"{where} · anotação", info.get(k, "")) for k in ("content", "title", "subject")
            ]
        for widget in page.widgets() or []:
            out.append((f"{where} · campo", str(widget.field_value or "")))
            out.append((f"{where} · campo", str(widget.field_name or "")))
        for link in page.get_links():
            if link.get("uri"):
                out.append((f"{where} · ligação", link["uri"]))
    return [(w, t) for w, t in out if t and t.strip()]


def harvest(path: Path) -> tuple[list[Seed], list[Finding], bool]:
    _open(path).close()
    return [], [], False


def texts(path: Path) -> list[tuple[str, str]]:
    doc = _open(path)
    try:
        return _document_texts(doc)
    finally:
        doc.close()


def _fit(text: str, rect: Any, size: float) -> float:
    width = pymupdf.get_text_length(text, fontname=_FONT, fontsize=size)
    return max(4.0, min(size, size * rect.width / width)) if width else size


def _redact_page(page: Any, engine: TextAnonymizer, where: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in _lines(page):
        text = "".join(c for c, _, _ in line)
        _, reps = engine.anonymize(text)
        for r in reps:
            rect = pymupdf.Rect(line[r.start][1])
            for _, bbox, _ in line[r.start : r.end]:
                rect |= bbox
            size = _fit(r.pseudonym, rect, line[r.start][2])
            page.add_redact_annot(
                rect, text=r.pseudonym, fontname=_FONT, fontsize=size, fill=(1, 1, 1)
            )
            findings.append(Finding("replaced", where, r.kind, 1, r.original, r.pseudonym))
    return findings


def transform_file(
    src: Path, dst: Path, engine: TextAnonymizer, strip_images: bool
) -> list[Finding]:
    doc = _open(src)
    findings: list[Finding] = []
    counts = {"annotations": 0, "signatures": 0, "image_metadata": 0, "images": 0}
    for pno, page in enumerate(doc, 1):
        where = f"pág. {pno}"
        for widget in list(page.widgets() or []):
            if widget.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                page.delete_widget(widget)
                counts["signatures"] += 1
                continue
            value = widget.field_value
            if isinstance(value, str) and value:
                new, reps = engine.anonymize(value)
                if reps:
                    widget.field_value = new
                    widget.update()
                    findings += [
                        Finding("replaced", f"{where} · campo", r.kind, 1, r.original, r.pseudonym)
                        for r in reps
                    ]
        for annot in list(page.annots() or []):
            page.delete_annot(annot)
            counts["annotations"] += 1
        for link in page.get_links():
            if link.get("uri"):
                new, reps = engine.anonymize(link["uri"])
                if reps:
                    link["uri"] = new
                    page.update_link(link)
        findings += _redact_page(page, engine, where)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE
        )
        for xref, *_ in page.get_images(full=True):
            counts["images"] += 1
            info = doc.extract_image(xref)
            if info and info.get("ext") in {"jpeg", "jpg"}:
                stripped = images.strip_metadata(info["image"])
                if stripped != info["image"]:
                    page.replace_image(xref, stream=stripped)
                    counts["image_metadata"] += 1
        chars = sum(len(line) for line in _lines(page))
        segments = sum(len(d["items"]) for d in page.get_drawings())
        if chars < _FEW_CHARS and segments > _VECTOR_DRAWINGS:
            findings.append(Finding("possible_vector_text", where))
    toc = doc.get_toc(simple=False)
    if toc:
        for entry in toc:
            entry[1] = engine.anonymize(entry[1])[0]
        doc.set_toc(toc)
    for name in doc.embfile_names():
        doc.embfile_del(name)
        findings.append(Finding("embedded_files_removed", f"anexo #{len(findings)}"))
    if any((doc.metadata or {}).values()) or doc.get_xml_metadata():
        doc.set_metadata({})
        doc.del_xml_metadata()
        findings.append(Finding("metadata_cleared"))
    for code, key in (
        ("annotations_removed", "annotations"),
        ("signatures_removed", "signatures"),
        ("image_metadata_removed", "image_metadata"),
    ):
        if counts[key]:
            findings.append(Finding(code, count=counts[key]))
    if counts["images"]:
        findings.append(Finding("images_present", count=counts["images"]))
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst), garbage=4, deflate=True, clean=True)
    doc.close()
    return findings


def scan_file(path: Path, checker: TextAnonymizer) -> list[Finding]:
    doc = _open(path)
    try:
        findings: list[Finding] = []
        for where, text in _document_texts(doc):
            for r in checker.residuals(text):
                code = "residual" if r.severity == "error" else "possible_name"
                findings.append(Finding(code, where, r.kind, original=r.value))
        # Every stream decompressed: catches values hidden outside the text layer.
        expanded = doc.tobytes(garbage=0, expand=255)
        for kind in sorted(set(checker.binary_hits(expanded))):
            findings.append(Finding("pii_in_binary", "conteúdo do PDF", kind))
        return findings
    finally:
        doc.close()
