"""Background jobs (RQ). Only the worker runs readers; the API only enqueues."""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

import redis
from fastapi import Depends
from rq import Queue
from sqlalchemy.orm import Session

import app.ingest.readers  # noqa: F401 - registers the processors
from app.config import Settings, get_settings
from app.db import session_factory
from app.ingest.pipeline import run_ingestion
from app.progress import Publish, redis_publisher
from app.storage import ObjectStore, make_s3_client

logger = logging.getLogger(__name__)

QUEUE = "ingest"
JOB_TIMEOUT_S = 900


@contextmanager
def _worker_session(settings: Settings) -> Iterator[Session]:
    session = session_factory(settings.database_url)()
    try:
        yield session
    finally:
        session.close()


def ingest_file(file_id: str) -> None:
    """RQ entry point."""
    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url)
    store = ObjectStore(make_s3_client(settings), settings.s3_bucket)
    with _worker_session(settings) as db:
        run_ingestion(db, store, redis_publisher(client), uuid.UUID(file_id))


class IngestQueue(Protocol):
    def enqueue(self, file_id: uuid.UUID) -> str | None: ...


@dataclass
class RQIngestQueue:
    queue: Queue

    def enqueue(self, file_id: uuid.UUID) -> str | None:
        try:
            job = self.queue.enqueue(ingest_file, str(file_id), job_timeout=JOB_TIMEOUT_S)
        except redis.RedisError as exc:
            logger.error("could not enqueue ingestion: %s", type(exc).__name__)
            return None
        return str(job.id)


def get_queue(settings: Annotated[Settings, Depends(get_settings)]) -> IngestQueue:
    return RQIngestQueue(Queue(QUEUE, connection=redis.Redis.from_url(settings.redis_url)))


def get_publisher(settings: Annotated[Settings, Depends(get_settings)]) -> Publish:
    publish = redis_publisher(redis.Redis.from_url(settings.redis_url))

    def safe(project_id: uuid.UUID, event: dict[str, Any]) -> None:
        try:
            publish(project_id, event)
        except redis.RedisError as exc:  # progress is best effort; the state is in the database
            logger.warning("could not publish progress: %s", type(exc).__name__)

    return safe
