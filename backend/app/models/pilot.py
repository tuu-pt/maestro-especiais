"""The pilot (Phase 8): time in the application, the estimate of the manual process, problems."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity
from app.models.enums import one_of

NOTE_STATUSES = ("open", "resolved")


class PilotTime(Entity):
    """Active seconds, summed from the heartbeats of the frontend (one row per day)."""

    __tablename__ = "pilot_time"
    __table_args__ = (UniqueConstraint("project_id", "user_id", "step", "day",
                                       name="uq_pilot_time"),)  # fmt: skip

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(64))
    step: Mapped[str] = mapped_column(String(20))
    day: Mapped[date] = mapped_column(Date)
    seconds: Mapped[int] = mapped_column(Integer, default=0)


class PilotBaseline(Entity):
    """How long the project would take by hand, step by step, written by the technician."""

    __tablename__ = "pilot_baseline"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), unique=True
    )
    steps: Mapped[dict[str, Any]] = mapped_column(default=dict)  # step -> [min, max] minutes
    rounds: Mapped[int | None] = mapped_column(Integer)  # rounds of corrections, usually
    errors: Mapped[str | None] = mapped_column(Text)  # the errors that appear most often
    typology: Mapped[str | None] = mapped_column(String(120))
    updated_by: Mapped[str | None] = mapped_column(String(64))


class PilotNote(Entity):
    """A problem found during the pilot, written on any screen (a block to fix, a wrong alert…)."""

    __tablename__ = "pilot_note"
    __table_args__ = (one_of("status", NOTE_STATUSES, "ck_pilot_note_status"),)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL")
    )
    screen: Mapped[str] = mapped_column(String(60))
    step: Mapped[str | None] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
