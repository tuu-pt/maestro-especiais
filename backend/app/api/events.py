import uuid
from collections.abc import AsyncIterator, Callable
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.projects import get_project
from app.auth import CurrentUser
from app.config import Settings, get_settings
from app.db import get_session
from app.progress import file_event, project_events

router = APIRouter(prefix="/projects", tags=["progresso"])

RedisFactory = Callable[[], aioredis.Redis]


def get_async_redis(settings: Annotated[Settings, Depends(get_settings)]) -> RedisFactory:
    return lambda: aioredis.Redis.from_url(settings.redis_url)


@router.get("/{project_id}/events")
async def events(
    project_id: uuid.UUID,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
    make_redis: Annotated[RedisFactory, Depends(get_async_redis)],
) -> EventSourceResponse:
    """Server-sent events with the ingestion state of every file of the project."""
    project = get_project(db, project_id)
    initial = [file_event(f) for f in project.files]

    async def stream() -> AsyncIterator[dict[str, str]]:
        client = make_redis()
        try:
            async for message in project_events(client, project_id, initial):
                yield message
        finally:
            await client.aclose()

    return EventSourceResponse(stream(), ping=15)
