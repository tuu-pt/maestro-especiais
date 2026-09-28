"""LLM calls and the names the privacy guard blocks (SPEC 6.1, P9; Phase 4)."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity
from app.models.enums import LLM_CALL_STATUSES, one_of


class LlmCall(Entity):
    """One request to the LLM. Never its content: who, what for, how long, how it ended."""

    __tablename__ = "llm_call"
    __table_args__ = (one_of("status", LLM_CALL_STATUSES, "ck_llm_call_status"),)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL")
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("section.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(20))  # drafting | extraction
    prompt_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)  # our message, never the model's text
    blocked: Mapped[list[Any]] = mapped_column(default=list)  # [{kind, where}], never the value


class BlockedTerm(Entity):
    """A name that must never reach the LLM: TUU team, technicians (profiles), admin list."""

    __tablename__ = "blocked_term"
    __table_args__ = (UniqueConstraint("value", name="uq_blocked_term_value"),)

    value: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="name")  # name | other
    source: Mapped[str] = mapped_column(String(20))  # fixtures | admin | profile
