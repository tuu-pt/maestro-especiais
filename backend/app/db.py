"""Database engine, sessions and the declarative base."""

import uuid
from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from typing import Any, ClassVar

from sqlalchemy import DateTime, Engine, String, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
        uuid.UUID: UUID(as_uuid=True),
    }


class Entity(Base):
    """Columns every table has (SPEC 7): id, created_at, updated_at, created_by."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String(64))


@lru_cache
def engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    return engine_for(get_settings().database_url)


@lru_cache
def session_factory(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=engine_for(url), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, committed by the endpoint."""
    session = session_factory(get_settings().database_url)()
    try:
        yield session
    finally:
        session.close()
