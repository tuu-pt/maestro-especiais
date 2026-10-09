"""The pilot (Phase 8): time spent in the application per project, step, person and day."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity


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
