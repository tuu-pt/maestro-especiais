"""Run the reader of a file and hand its result to the ficha-base (SPEC 8.1, steps 1 and 2).

Readers register a processor per file kind. A processor returns a short summary for people
(counts, warnings) and must never put values from the file in it.
"""

import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.audit import record
from app.models import ProjectFile
from app.progress import Publish, file_event
from app.storage import ObjectStore

logger = logging.getLogger(__name__)

Processor = Callable[[Session, ProjectFile, bytes], str]
PROCESSORS: dict[str, Processor] = {}


class ReaderError(Exception):
    """A problem the reader explains to people (e.g. unknown template version). No values."""


def register(kind: str) -> Callable[[Processor], Processor]:
    def decorator(processor: Processor) -> Processor:
        PROCESSORS[kind] = processor
        return processor

    return decorator


def _set(db: Session, publish: Publish, file: ProjectFile, status: str, message: str | None,
         step: str | None = None) -> None:  # fmt: skip
    file.ingest_status = status
    file.ingest_message = message
    db.commit()
    publish(file.project_id, file_event(file, step))


def run_ingestion(db: Session, store: ObjectStore, publish: Publish, file_id: uuid.UUID) -> None:
    file = db.get(ProjectFile, file_id)
    if file is None:
        logger.warning("ingest: file %s no longer exists", file_id)
        return
    processor = PROCESSORS.get(file.kind)
    if processor is None:
        _set(db, publish, file, "skipped", "Leitura deste tipo na Fase 2.")
        return
    _set(db, publish, file, "running", None, step="A ler o ficheiro")
    try:
        summary = processor(db, file, store.get(file.storage_key))
    except ReaderError as exc:
        db.rollback()
        _fail(db, publish, file, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - reported without the message, which may hold values
        db.rollback()
        logger.error("ingest failed: file=%s error=%s", file_id, type(exc).__name__)
        _fail(db, publish, file, f"Não foi possível ler o ficheiro ({type(exc).__name__}).")
        return
    record(db, None, "file.ingested", "project_file", file.id,
           {"kind": file.kind, "summary": summary}, project_id=file.project_id)  # fmt: skip
    _set(db, publish, file, "done", summary)


def _fail(db: Session, publish: Publish, file: ProjectFile, message: str) -> None:
    file = db.merge(file)
    record(db, None, "file.ingest_failed", "project_file", file.id,
           {"kind": file.kind}, project_id=file.project_id)  # fmt: skip
    _set(db, publish, file, "failed", message)
