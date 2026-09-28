"""Drafting in the background (RQ queue "llm"), with progress on the project's SSE channel.

draft_document drafts every active section with adaptive paragraphs that has no text from the
agent yet (no current or proposed version by the agent): a run that stopped (daily quota, an
error) resumes from the first section still to draft. Events: queued (waiting for the quota
pace), generating, generated, failed, paused.
"""

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

import redis
from fastapi import Depends
from rq import Queue
from sqlalchemy.orm import Session

from app.audit import record
from app.config import Settings, get_settings
from app.drafting.draft import DraftRefused, adaptive_entries, draft_section
from app.llm.client import LlmClient, LlmFailed, LlmPaused, make_provider
from app.llm.guard import PrivacyBlocked
from app.llm.ratelimit import RedisRateLimiter
from app.models import Document, Section, TemplateBlock
from app.progress import Publish, redis_publisher

logger = logging.getLogger(__name__)
QUEUE = "llm"
JOB_TIMEOUT_S = 3600


def section_event(section: Section, status: str, message: str | None = None,
                  wait_s: float | None = None) -> dict[str, Any]:  # fmt: skip
    return {"type": "section", "document_id": str(section.document_id),
            "section_id": str(section.id), "title": section.title, "status": status,
            "message": message, "wait_s": wait_s}  # fmt: skip


def to_draft(db: Session, document: Document) -> list[Section]:
    out = []
    for s in document.sections:
        block = db.get(TemplateBlock, s.block_id) if s.block_id else None
        if not s.active or block is None or not adaptive_entries(block):
            continue
        if any(
            v.author_type == "agent" and v.status in ("current", "proposed") for v in s.versions
        ):
            continue  # already drafted: resume after it
        out.append(s)
    return out


def run_one(db: Session, client: LlmClient, publish: Publish, section: Section,
            project_id: uuid.UUID, request: str | None = None) -> bool:  # fmt: skip
    """Draft one section. False when the daily quota stops the run."""
    client.on_wait = lambda s: publish(project_id, section_event(section, "queued", wait_s=s))
    publish(project_id, section_event(section, "generating"))
    try:
        version = draft_section(db, client, section, request)
    except LlmPaused as exc:
        db.commit()
        publish(project_id, section_event(section, "paused", str(exc)))
        return False
    except (LlmFailed, PrivacyBlocked, DraftRefused) as exc:
        section.status, section.status_note = "todo", str(exc)
        db.commit()
        publish(project_id, section_event(section, "failed", str(exc)))
        return True
    record(db, None, "section.draft_proposed", "section", section.id,
           {"title": section.title, "version": version.number, "request": bool(request)},
           project_id=project_id, actor_type="agent")  # fmt: skip
    db.commit()
    publish(project_id, section_event(section, "generated"))
    return True


def draft_document(db: Session, client: LlmClient, publish: Publish, document_id: uuid.UUID
                   ) -> dict[str, int]:  # fmt: skip
    document = db.get(Document, document_id)
    if document is None:
        return {"drafted": 0}
    sections = to_draft(db, document)
    for s in sections:
        publish(document.project_id, section_event(s, "queued"))
    done = 0
    for s in sections:
        if not run_one(db, client, publish, s, document.project_id):
            break
        done += 1
    return {"drafted": done, "pending": len(sections) - done}


# ---------------------------------------------------------------- RQ


def _client(settings: Settings, connection: redis.Redis) -> LlmClient:
    limiter = RedisRateLimiter(connection, settings.llm_rpm, settings.llm_rpd)
    return LlmClient(make_provider(settings), limiter, settings, sleep=time.sleep)


def _session(settings: Settings) -> Session:
    from app.db import session_factory

    return session_factory(settings.database_url)()


def document_job(document_id: str) -> None:
    settings = get_settings()
    connection = redis.Redis.from_url(settings.redis_url)
    with _session(settings) as db:
        draft_document(db, _client(settings, connection), redis_publisher(connection),
                       uuid.UUID(document_id))  # fmt: skip


def section_job(section_id: str, request: str | None) -> None:
    settings = get_settings()
    connection = redis.Redis.from_url(settings.redis_url)
    with _session(settings) as db:
        section = db.get(Section, uuid.UUID(section_id))
        if section is not None:
            run_one(db, _client(settings, connection), redis_publisher(connection), section,
                    section.document.project_id, request)  # fmt: skip


class DraftQueue(Protocol):
    def document(self, document_id: uuid.UUID) -> str | None: ...

    def section(self, section_id: uuid.UUID, request: str | None) -> str | None: ...


@dataclass
class RQDraftQueue:
    queue: Queue

    def _enqueue(self, fn: Callable[..., None], *args: Any) -> str | None:
        try:
            return str(self.queue.enqueue(fn, *args, job_timeout=JOB_TIMEOUT_S).id)
        except redis.RedisError as exc:
            logger.error("could not enqueue drafting: %s", type(exc).__name__)
            return None

    def document(self, document_id: uuid.UUID) -> str | None:
        return self._enqueue(document_job, str(document_id))

    def section(self, section_id: uuid.UUID, request: str | None) -> str | None:
        return self._enqueue(section_job, str(section_id), request)


def get_draft_queue(settings: Annotated[Settings, Depends(get_settings)]) -> DraftQueue:
    return RQDraftQueue(Queue(QUEUE, connection=redis.Redis.from_url(settings.redis_url)))
