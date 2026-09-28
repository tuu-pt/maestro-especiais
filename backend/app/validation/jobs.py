"""Validation in the background (RQ queue "validation"), with progress on the SSE channel."""

import logging
import uuid
from dataclasses import dataclass
from typing import Annotated, Protocol

import redis
from fastapi import Depends
from rq import Queue
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.progress import redis_publisher
from app.storage import ObjectStore, make_s3_client

logger = logging.getLogger(__name__)
QUEUE = "validation"
JOB_TIMEOUT_S = 900


def validation_job(run_id: str) -> None:
    """RQ entry point."""
    from app.db import session_factory
    from app.validation.engine import run_validation

    settings = get_settings()
    connection = redis.Redis.from_url(settings.redis_url)
    store = ObjectStore(make_s3_client(settings), settings.s3_bucket)
    with session_factory(settings.database_url)() as db:
        run_validation(db, store, settings, redis_publisher(connection), uuid.UUID(run_id))


class ValidationQueue(Protocol):
    def enqueue(self, run_id: uuid.UUID) -> str | None: ...


@dataclass
class RQValidationQueue:
    queue: Queue

    def enqueue(self, run_id: uuid.UUID) -> str | None:
        try:
            job = self.queue.enqueue(validation_job, str(run_id), job_timeout=JOB_TIMEOUT_S)
        except redis.RedisError as exc:
            logger.error("could not enqueue validation: %s", type(exc).__name__)
            return None
        return str(job.id)


def get_validation_queue(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ValidationQueue:
    return RQValidationQueue(Queue(QUEUE, connection=redis.Redis.from_url(settings.redis_url)))


def revalidate(db: Session, queue: ValidationQueue, project_id: uuid.UUID,
               user_id: str | None) -> None:  # fmt: skip
    """After an edit: validate again the pieces that changed, if the project was validated."""
    from app.models import Project
    from app.validation.engine import latest, queue_run

    project = db.get(Project, project_id)
    if project is None or latest(db, project_id) is None:
        return
    run = queue_run(db, project, "changed", user_id)
    db.commit()
    if queue.enqueue(run.id) is None:
        run.status, run.message = "failed", "Revalidação não posta na fila."
        db.commit()
