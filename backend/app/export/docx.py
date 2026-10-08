"""MDJ and CTE as .docx: the draft with its watermark, or the official version (Phase 6).

Built by app.assembly.docx on the package of the template (the R1 document until TUU gives empty
templates [A CONFIRMAR]); the header gets the técnico, the date only if they wrote it (P8) and
the revision R<nn>; the document properties name TUU and the document, never people. With
LibreOffice, the index gets its page numbers and Word no longer asks to update the fields
(app.export.toc); the quick download of a draft skips it (`paginate=False`).
"""

import io
import re
import zipfile
from collections import Counter

from sqlalchemy.orm import Session

from app.assembly.assemble import omitted
from app.assembly.docx import Options, by_entry, draft_docx
from app.assembly.values import ValueSource
from app.config import Settings
from app.export import (
    SUBJECTS,
    TITLES,
    WATERMARK,
    Exported,
    ExportRefused,
    draft_name,
    official_name,
)
from app.export.toc import paginate as paginate_toc
from app.models import Document, FichaRevision, Project, TemplateBlock
from app.profiles import revision_profile
from app.review import conditions, file_version, header_revision
from app.storage import ObjectStore

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
IMAGE_TAGS = ("<a:blip ", "<v:imagedata ")


def ooxml_counts(ooxml: str) -> Counter[str]:
    """Images, formulas and tables of an OOXML fragment, counted on its text."""
    return Counter(
        images=sum(ooxml.count(t) for t in IMAGE_TAGS),
        formulas=ooxml.count("<m:oMath>") + ooxml.count("<m:oMath "),
        tables=ooxml.count("<w:tbl>") + ooxml.count("<w:tbl "),
    )


def expected_counts(db: Session, document: Document) -> Counter[str]:
    """What the export must carry: the entries of the source sections that leave as OOXML."""
    total: Counter[str] = Counter(images=0, formulas=0, tables=0)
    for section in document.sections:
        block = db.get(TemplateBlock, section.block_id) if section.block_id else None
        if not section.active or block is None:
            continue
        version = next(v for v in section.versions if v.number == section.current_version)
        first = next((v for v in section.versions if v.number == 1), version)
        now = by_entry(version.content.get("content") or [])
        assembled = by_entry(first.content.get("content") or [])
        for i, entry in enumerate(block.body_template):
            if omitted(entry) or entry["mode"] == "adaptive" or not entry.get("ooxml"):
                continue
            if now.get(i, []) == assembled.get(i, []):
                total += ooxml_counts(entry["ooxml"])
    return total


def _visible_xml(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist()
                 if n.startswith(("word/document", "word/header", "word/footer"))]  # fmt: skip
        return "".join(z.read(n).decode("utf-8", "replace") for n in names)


def export_docx(db: Session, store: ObjectStore, settings: Settings, document: Document, *,
                official: bool, paginate: bool = True) -> Exported:  # fmt: skip
    project = db.get(Project, document.project_id)
    revision = db.get(FichaRevision, document.ficha_revision_id)
    assert project is not None and revision is not None
    if document.origin != "assembled":
        raise ExportRefused(["Peça existente (auditoria): só se valida, não se exporta."])
    if official:
        reasons = [c.reason or c.text for c in conditions(db, document) if not c.ok]
        if document.status != "approved":
            reasons.append("A peça ainda não foi aprovada pelo técnico responsável.")
        if reasons:
            raise ExportRefused(reasons)
    values = ValueSource.load(db, revision, revision_profile(db, settings, revision))
    options = Options(
        revision=header_revision(document.revision),
        header_date=document.header_date,
        watermark=None if official else WATERMARK,
        title=f"{project.code} · {TITLES.get(document.type, document.type)}",
        subject=SUBJECTS.get(project.phase, SUBJECTS["execucao"]),
    )
    data = draft_docx(db, store, document, values, options)
    if paginate:
        data = paginate_toc(data) or data
    missing = sorted(set(re.findall(r"\[falta: ([^\]]+)\]", _visible_xml(data))))
    if official and missing:  # labels only, never values
        raise ExportRefused([f"Há valores em falta no {document.type}: {', '.join(missing)}."])
    name = (official_name(project.code, document.type, project.phase,
                          file_version(document.revision), "docx")
            if official else draft_name(project.code, document.type, "docx"))  # fmt: skip
    return Exported(name, data, DOCX)
