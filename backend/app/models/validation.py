"""Validation runs, their issues and the facts read from each piece (SPEC 7.4; Phase 5).

An issue never carries a personal value: its evidence is masked when it is built. The facts of
a piece are cached by the hash of its content, so a revalidation after an edit only reads the
pieces that changed.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import (
    ISSUE_SEVERITIES,
    ISSUE_STATUSES,
    RUN_STATUSES,
    RUN_TRIGGERS,
    one_of,
)


class ValidationRun(Entity):
    __tablename__ = "validation_run"
    __table_args__ = (
        one_of("status", RUN_STATUSES, "ck_validation_run_status"),
        one_of("trigger", RUN_TRIGGERS, "ck_validation_run_trigger"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    ficha_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ficha_revision.id", ondelete="SET NULL")
    )
    document_ids: Mapped[list[Any]] = mapped_column(default=list)
    pieces: Mapped[list[Any]] = mapped_column(default=list)  # [{ref, kind, label, …}]
    trigger: Mapped[str] = mapped_column(String(10), default="full")  # full | changed
    status: Mapped[str] = mapped_column(String(10), default="queued")
    message: Mapped[str | None] = mapped_column(Text)  # ours, never values from the pieces
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totals: Mapped[dict[str, Any]] = mapped_column(default=dict)
    matrix: Mapped[dict[str, Any]] = mapped_column(default=dict)  # SPEC 10.E, masked

    issues: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="run", order_by="ValidationIssue.order"
    )


class ValidationIssue(Entity):
    __tablename__ = "validation_issue"
    __table_args__ = (
        one_of("severity", ISSUE_SEVERITIES, "ck_validation_issue_severity"),
        one_of("status", ISSUE_STATUSES, "ck_validation_issue_status"),
        Index("ix_validation_issue_run", "run_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("validation_run.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column(default=0)
    rule_id: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(30))
    # same finding in two runs → same fingerprint: an ignored issue stays ignored
    fingerprint: Mapped[str] = mapped_column(String(64))
    location: Mapped[dict[str, Any]] = mapped_column(default=dict)
    message_pt: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(default=dict)
    likely_reading: Mapped[str | None] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[list[Any]] = mapped_column(default=list)
    new: Mapped[bool] = mapped_column(default=True)  # not in the previous run
    status: Mapped[str] = mapped_column(String(10), default="open")
    ignored_reason: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[ValidationRun] = relationship(back_populates="issues")


class PieceFacts(Entity):
    """What the extractors read from one piece, by the hash of its content."""

    __tablename__ = "piece_facts"
    __table_args__ = (UniqueConstraint("project_id", "piece_ref", name="uq_piece_facts_ref"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    piece_ref: Mapped[str] = mapped_column(String(60))  # doc:<uuid> | file:<uuid> | calc | …
    content_hash: Mapped[str] = mapped_column(String(64))
    extractor_version: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)  # facts, paragraphs, sections
