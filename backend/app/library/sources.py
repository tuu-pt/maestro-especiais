"""Reference MDJ/CTE into the library: package and media in S3, sections in the database.

Idempotent by content: a document already stored (same SHA-256) is left as it is. When the file of
a project changes, its previous version (same project and document type) is replaced.

S3 keys never carry file names: library/sources/<sha256>.docx and library/media/<sha256>.
"""

from collections.abc import Iterator
from pathlib import Path

import docx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge.sources import docx_kind, unique_files
from app.library.docx_blocks import split
from app.models import SourceDocument, SourceSection
from app.storage import ObjectStore

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def package_key(sha256: str) -> str:
    return f"library/sources/{sha256}.docx"


def media_key(sha256: str) -> str:
    return f"library/media/{sha256}"


def store_source(
    db: Session, store: ObjectStore, project_code: str, doc_type: str, file: str, data: bytes
) -> SourceDocument:
    parts = split(data)
    existing = db.scalars(
        select(SourceDocument).where(SourceDocument.sha256 == parts.sha256)
    ).first()
    if existing is not None:
        return existing
    for old in db.scalars(
        select(SourceDocument).where(
            SourceDocument.project_code == project_code, SourceDocument.doc_type == doc_type
        )
    ):
        db.delete(old)  # the fixture changed: its sections go with it
    db.flush()
    store.put(package_key(parts.sha256), parts.package, DOCX)
    for digest, blob in parts.media.items():
        store.put(media_key(digest), blob)
    document = SourceDocument(
        project_code=project_code, doc_type=doc_type, file=file, sha256=parts.sha256,
        size=len(data), package_key=package_key(parts.sha256), warnings=parts.warnings,
        sections=[
            SourceSection(
                order=s.order, kind=s.kind, level=s.level, key=s.key, title=s.title[:200],
                ooxml=s.ooxml, text=s.text, stats=s.stats(),
                rels={rid: vars(rel) for rid, rel in s.rels.items()},
            )
            for s in parts.sections
        ],
    )  # fmt: skip
    db.add(document)
    db.flush()
    return document


def reference_documents(fixtures: Path, code: str) -> Iterator[tuple[str, str, bytes]]:
    """(doc_type, path inside the project, bytes) of each MDJ and CTE of a reference project."""
    root = fixtures / code
    for path in unique_files(root):
        if path.suffix.lower() == ".docx":
            kind = docx_kind(docx.Document(str(path)))
            if kind:
                yield kind, path.relative_to(root).as_posix(), path.read_bytes()


def seed_sources(
    db: Session, store: ObjectStore, fixtures: Path, codes: tuple[str, ...]
) -> dict[str, int]:
    documents = sections = 0
    for code in codes:
        if not (fixtures / code).is_dir():
            continue
        for doc_type, file, data in reference_documents(fixtures, code):
            document = store_source(db, store, code, doc_type, file, data)
            documents += 1
            sections += len(document.sections)
    return {"source_documents": documents, "source_sections": sections}
