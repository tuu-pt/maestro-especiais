"""Project and ProjectFile (SPEC 7.1)."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import FILE_KINDS, INGEST_STATUSES, PROJECT_PHASES, PROJECT_STATUSES, one_of


class Project(Entity):
    __tablename__ = "project"
    __table_args__ = (
        one_of("phase", PROJECT_PHASES, "ck_project_phase"),
        one_of("status", PROJECT_STATUSES, "ck_project_status"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    building_type: Mapped[str | None] = mapped_column(String(120))
    phase: Mapped[str] = mapped_column(String(20), default="execucao")
    specialties: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=lambda: ["ELE"])
    public_procurement: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")

    files: Mapped[list["ProjectFile"]] = relationship(
        back_populates="project", order_by="ProjectFile.created_at"
    )


class ProjectFile(Entity):
    __tablename__ = "project_file"
    __table_args__ = (
        UniqueConstraint("project_id", "checksum", name="uq_project_file_checksum"),
        one_of("kind", FILE_KINDS, "ck_project_file_kind"),
        one_of("ingest_status", INGEST_STATUSES, "ck_project_file_ingest_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32), default="other")
    # The original name may contain personal data: it is never used as a storage key.
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(64))  # SHA-256, hex
    version_label: Mapped[str | None] = mapped_column(String(20))
    file_date: Mapped[date | None] = mapped_column(Date)
    template_version: Mapped[str | None] = mapped_column(String(40))
    ingest_status: Mapped[str] = mapped_column(String(20), default="pending")
    # Message for people, never with values from the file.
    ingest_message: Mapped[str | None] = mapped_column(Text)
    # Warnings of the last reading, for people (never values from the file).
    ingest_warnings: Mapped[list[Any]] = mapped_column(default=list, server_default="[]")

    project: Mapped[Project] = relationship(back_populates="files")
