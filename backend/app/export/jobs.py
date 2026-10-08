"""Exports in the background (RQ queue "export"), with progress on the SSE channel."""

import logging
import uuid
from dataclasses import dataclass
from typing import Annotated, Protocol

import redis
from fastapi import Depends
from rq import Queue

from app.config import Settings, get_settings
from app.progress import redis_publisher
from app.storage import ObjectStore, make_s3_client

logger = logging.getLogger(__name__)
QUEUE = "export"
JOB_TIMEOUT_S = 1800  # a PDF of each piece through LibreOffice can be slow


def export_job(export_id: str) -> None:
    """RQ entry point."""
    from app.db import session_factory
    from app.export.bundle import run_export

    settings = get_settings()
    connection = redis.Redis.from_url(settings.redis_url)
    store = ObjectStore(make_s3_client(settings), settings.s3_bucket)
    with session_factory(settings.database_url)() as db:
        run_export(db, store, settings, redis_publisher(connection), uuid.UUID(export_id))


class ExportQueue(Protocol):
    def enqueue(self, export_id: uuid.UUID) -> str | None: ...


@dataclass
class RQExportQueue:
    queue: Queue

    def enqueue(self, export_id: uuid.UUID) -> str | None:
        try:
            job = self.queue.enqueue(export_job, str(export_id), job_timeout=JOB_TIMEOUT_S)
        except redis.RedisError as exc:
            logger.error("could not enqueue export: %s", type(exc).__name__)
            return None
        return str(job.id)


def get_export_queue(settings: Annotated[Settings, Depends(get_settings)]) -> ExportQueue:
    return RQExportQueue(Queue(QUEUE, connection=redis.Redis.from_url(settings.redis_url)))
