"""Audit log writer (SPEC P7). Insert-only; payloads never carry personal values."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.auth import User
from app.models import AuditEvent


def record(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
    *,
    actor_type: str | None = None,
) -> AuditEvent:
    """Add one event to the session. actor None means the system (e.g. the ingestion worker)."""
    event = AuditEvent(
        actor_type=actor_type or ("user" if actor else "system"),
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    db.add(event)
    return event
