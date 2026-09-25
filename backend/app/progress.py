"""Ingestion progress: the worker publishes on Redis, the API streams it as SSE.

Events carry ids, kinds, statuses and our own messages: never values from the files.
"""

import json
import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from typing import Any

import redis
import redis.asyncio as aioredis

from app.models import ProjectFile

Publish = Callable[[uuid.UUID, dict[str, Any]], None]


def channel(project_id: uuid.UUID) -> str:
    return f"project:{project_id}:events"


def file_event(file: ProjectFile, step: str | None = None) -> dict[str, Any]:
    return {
        "file_id": str(file.id),
        "kind": file.kind,
        "status": file.ingest_status,
        "message": file.ingest_message,
        "warnings": list(file.ingest_warnings or []),
        "step": step,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def redis_publisher(client: redis.Redis) -> Publish:
    def publish(project_id: uuid.UUID, event: dict[str, Any]) -> None:
        client.publish(channel(project_id), json.dumps(event))

    return publish


def no_publish(project_id: uuid.UUID, event: dict[str, Any]) -> None:
    return None


async def project_events(
    client: aioredis.Redis, project_id: uuid.UUID, initial: list[dict[str, Any]]
) -> AsyncGenerator[dict[str, str]]:
    """Current state of every file first, then live updates, as SSE messages."""
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(project_id))
    try:
        for event in initial:
            yield {"event": "file", "data": json.dumps(event)}
        async for message in pubsub.listen():
            if message.get("type") == "message":
                data = message["data"]
                yield {"event": "file", "data": data.decode() if isinstance(data, bytes) else data}
    finally:
        await pubsub.unsubscribe(channel(project_id))
        await pubsub.aclose()  # type: ignore[no-untyped-call]
