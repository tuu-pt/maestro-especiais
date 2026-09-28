"""Written pieces made by hand (Word): MDJ, CTE, identification and term (Phase 5).

They are uploaded to audit a project (SPEC 10.E) and validated like the pieces the tool
assembles. The kind is found by content (the title), never by the file name.
"""

from collections.abc import Iterator
from itertools import islice
from typing import Any

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.detect import fold
from app.ingest.pipeline import ReaderError
from app.library import docx_blocks
from app.library.facts import cover_facts, signature_facts
from app.models import Document, ProjectFile, Section, SectionVersion

# kind found in the document -> ProjectFile.kind
FILE_KINDS = {
    "MDJ": "mdj_docx",
    "CTE": "cte_docx",
    "IDENTIFICACAO": "identificacao_docx",
    "TERMO": "termo_docx",
}
DOCUMENT_TYPE_OF_KIND = {v: k for k, v in FILE_KINDS.items()}


def docx_texts(document: DocxDocument) -> Iterator[tuple[str, str]]:
    """(locator, text) of every paragraph of the body, in order, tables included."""
    body = document.element.body
    for n, element in enumerate(body.iterchildren(), start=1):
        if element.tag == qn("w:p"):
            text = "".join(t.text or "" for t in element.iter(qn("w:t")))
            if text.strip():
                yield f"parágrafo {n}", text
        elif element.tag == qn("w:tbl"):
            for r, row in enumerate(element.iter(qn("w:tr")), start=1):
                for c, cell in enumerate(row.iter(qn("w:tc")), start=1):
                    text = "".join(t.text or "" for t in cell.iter(qn("w:t")))
                    if text.strip():
                        yield f"tabela no elemento {n}, linha {r}, célula {c}", text


def piece_kind(document: DocxDocument) -> str | None:
    """MDJ, CTE, IDENTIFICACAO or TERMO, from the title (the first paragraphs)."""
    head = fold(" ".join(p.text for p in document.paragraphs[:40]))
    if "memoria descritiva" in head:
        return "MDJ"
    if "condicoes tecnicas" in head or "caderno de encargos" in head:
        return "CTE"
    # the forms have their title in a table
    head += " " + fold(" ".join(text for _, text in islice(docx_texts(document), 60)))
    if "termo de responsabilidade" in head:
        return "TERMO"
    if "identificacao do projeto" in head:
        return "IDENTIFICACAO"
    return None


def section_lines(elements: list[Any]) -> list[str]:
    """One line per paragraph; a table gives one line per row, cells joined by " | "."""
    lines = []
    for e in elements:
        if e.tag == qn("w:tbl"):
            for row in e.iter(qn("w:tr")):
                cells = ["".join(t.text or "" for t in c.iter(qn("w:t"))).strip()
                         for c in row.iter(qn("w:tc"))]  # fmt: skip
                cells = [c for i, c in enumerate(cells) if c and c not in cells[:i]]
                if cells:
                    lines.append(" | ".join(cells))
        elif e.tag == qn("w:p"):
            line = "".join(t.text or "" for t in e.iter(qn("w:t")))
            if line.strip():
                lines.append(line)
    return lines


def add_existing(db: Session, file: ProjectFile, data: bytes) -> str:
    """The MDJ or CTE made by hand, as a read-only Document split in sections (Phase 3 split).

    What is stored for the screens is masked (the requerente and the technician are in the
    clear in the file); the validation reads the file itself, in the backend.
    """
    from app.ingest.consolidate import draft_revision, latest_revision
    from app.validation.masking import Masker, project_personal_values

    doc_type = DOCUMENT_TYPE_OF_KIND[file.kind]
    try:
        parts = docx_blocks.split(data)
    except docx_blocks.DocxError as exc:
        raise ReaderError(str(exc)) from exc
    revision = latest_revision(db, file.project_id) or draft_revision(db, file.project_id, None)
    masker = Masker(project_personal_values(db, file.project_id))
    for s in parts.sections:
        if s.kind in ("cover", "signature"):
            lines = section_lines(s.elements)
            masker.add(f.value for f in cover_facts(lines) + signature_facts(lines))
    for old in db.scalars(select(Document).where(
        Document.project_id == file.project_id, Document.origin == "existing",
        Document.type == doc_type,
    )):  # fmt: skip
        db.delete(old)  # a new upload of the same piece replaces the previous one
    document = Document(project_id=file.project_id, type=doc_type, origin="existing",
                        source_file_id=file.id, ficha_revision_id=revision.id)  # fmt: skip
    db.add(document)
    prefix = f"ele.{doc_type.lower()}."
    for s in parts.sections:
        nodes = [{"type": "paragraph", "attrs": {"anchor": f"p{i}", "readonly": True},
                  "content": [{"type": "text", "text": masker(line)}]}
                 for i, line in enumerate(section_lines(s.elements))]  # fmt: skip
        document.sections.append(Section(
            block_key=prefix + s.key, block_version=0, block_status="existing", order=s.order,
            title=s.title, level=s.level, kind=s.kind, mode="fixed", locked=True,
            status="todo", active=True,
            versions=[SectionVersion(number=1, author_type="system", status="current",
                                     content={"type": "doc", "content": nodes})],
        ))  # fmt: skip
    warned = f" · {len(parts.warnings)} avisos" if parts.warnings else ""
    file.ingest_warnings = list(parts.warnings)
    return f"{doc_type} existente: {len(parts.sections)} secções (só leitura){warned}"
