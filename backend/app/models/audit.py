"""AuditEvent (SPEC 7.7): insert-only. A database trigger rejects UPDATE, DELETE and TRUNCATE."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import ACTOR_TYPES, one_of


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (one_of("actor_type", ACTOR_TYPES, "ck_audit_event_actor_type"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # clock_timestamp(), not now(): events of one transaction keep their real order.
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    actor_type: Mapped[str] = mapped_column(String(10))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None]
    # Never personal values: ids, keys, counts and non-personal labels only.
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
