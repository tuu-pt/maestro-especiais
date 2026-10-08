"""An export of the pieces of a project (Phase 6): a draft or the official set, in the S3 bucket.

Each file is kept with its hash and its version (SPEC 11); the names of the files live only here,
never in the storage keys. Built in the background (RQ queue "export").
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity
from app.models.enums import one_of

EXPORT_KINDS = ("draft", "official")
EXPORT_STATUSES = ("queued", "running", "done", "failed")


class Export(Entity):
    __tablename__ = "export"
    __table_args__ = (
        one_of("kind", EXPORT_KINDS, "ck_export_kind"),
        one_of("status", EXPORT_STATUSES, "ck_export_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="queued")
    message: Mapped[str | None] = mapped_column(Text)  # ours, never values of the pieces
    with_pdf: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[str] = mapped_column(String(10), default="V0")  # of the set (official)
    # [{"name", "piece", "kind", "revision", "key", "sha256", "size", "media_type"}]
    files: Mapped[list[Any]] = mapped_column(default=list)
    manifest: Mapped[dict[str, Any]] = mapped_column(default=dict)
    zip_name: Mapped[str | None] = mapped_column(String(200))
    zip_key: Mapped[str | None] = mapped_column(String(200))
    zip_sha256: Mapped[str | None] = mapped_column(String(64))
    zip_size: Mapped[int | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
