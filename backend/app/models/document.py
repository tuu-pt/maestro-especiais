"""Documents of a project assembled from the block library (SPEC 7.3, Phase 4).

A Document (MDJ or CTE) is assembled from a confirmed ficha-base revision. Each Section comes
from one TemplateBlock (its key, version and review status are kept, so that a section built on
a block not yet approved says so). The text lives in SectionVersion (TipTap JSON): a version
written by the agent is "proposed" until a person accepts it; nothing replaces the current
version without a human action.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import (
    ACTOR_TYPES,
    BLOCK_MODES,
    DOCUMENT_STATUSES,
    DOCUMENT_TYPES,
    SECTION_KINDS,
    SECTION_STATUSES,
    VERSION_STATUSES,
    one_of,
)


class Document(Entity):
    __tablename__ = "document"
    __table_args__ = (
        one_of("type", DOCUMENT_TYPES, "ck_document_type"),
        one_of("status", DOCUMENT_STATUSES, "ck_document_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(15))  # MDJ | CTE (forms: Phase 4, task 6)
    specialty: Mapped[str] = mapped_column(String(20), default="ele")
    # the package (styles, numbering, headers) the draft .docx is built on [A CONFIRMAR]
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_document.id", ondelete="SET NULL")
    )
    ficha_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ficha_revision.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(15), default="draft")
    responsible_user_id: Mapped[str | None] = mapped_column(String(64))

    sections: Mapped[list["Section"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Section.order"
    )


class Section(Entity):
    __tablename__ = "section"
    __table_args__ = (
        UniqueConstraint("document_id", "order", name="uq_section_order"),
        one_of("status", SECTION_STATUSES, "ck_section_status"),
        one_of("mode", BLOCK_MODES, "ck_section_mode"),
        one_of("kind", SECTION_KINDS, "ck_section_kind"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("template_block.id", ondelete="SET NULL")
    )
    block_key: Mapped[str] = mapped_column(String(200))
    block_version: Mapped[int] = mapped_column(Integer)
    block_status: Mapped[str] = mapped_column(String(10))  # proposed | approved | rejected
    order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    mode: Mapped[str] = mapped_column(String(10))
    # result of the activation rule; a person may change it with a reason (activation_override)
    active: Mapped[bool] = mapped_column(default=True)
    active_reason: Mapped[str | None] = mapped_column(Text)
    activation_override: Mapped[dict[str, Any] | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(10), default="todo")
    status_note: Mapped[str | None] = mapped_column(Text)  # e.g. "falta dado: Nome do técnico"
    missing_keys: Mapped[list[Any]] = mapped_column(default=list)
    locked: Mapped[bool] = mapped_column(default=False)  # fixed blocks
    unlocked: Mapped[dict[str, Any] | None] = mapped_column()  # {by, at, reason}
    equipment_slots: Mapped[list[Any]] = mapped_column(default=list)  # CTE, filled in Phase 7
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document] = relationship(back_populates="sections")
    versions: Mapped[list["SectionVersion"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="SectionVersion.number"
    )


class SectionVersion(Entity):
    __tablename__ = "section_version"
    __table_args__ = (
        UniqueConstraint("section_id", "number", name="uq_section_version_number"),
        one_of("author_type", ACTOR_TYPES, "ck_section_version_author_type"),
        one_of("status", VERSION_STATUSES, "ck_section_version_status"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("section.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column()  # TipTap JSON
    author_type: Mapped[str] = mapped_column(String(10))  # system | agent | user
    status: Mapped[str] = mapped_column(String(10), default="current")
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column()
    request: Mapped[str | None] = mapped_column(Text)  # the request in natural language, if any
    missing_data: Mapped[list[Any]] = mapped_column(default=list)
    assumptions: Mapped[list[Any]] = mapped_column(default=list)
    issues: Mapped[list[Any]] = mapped_column(default=list)  # NUM-01, REF-01…

    section: Mapped[Section] = relationship(back_populates="versions")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    value_refs: Mapped[list["ValueRef"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class Citation(Entity):
    __tablename__ = "citation"

    section_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("section_version.id", ondelete="CASCADE")
    )
    anchor: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(15))  # regulation | archive | block | calc | ficha
    target_id: Mapped[str] = mapped_column(String(200))
    locator: Mapped[str | None] = mapped_column(String(200))

    version: Mapped[SectionVersion] = relationship(back_populates="citations")


class ValueRef(Entity):
    """A value written into a section, with where it came from (SPEC 7.3)."""

    __tablename__ = "value_ref"

    section_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("section_version.id", ondelete="CASCADE")
    )
    anchor: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(120))  # the placeholder key
    ficha_value_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ficha_value.id", ondelete="SET NULL")
    )
    circuit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("circuit.id", ondelete="SET NULL")
    )
    bom_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bom_item.id", ondelete="SET NULL")
    )
    field: Mapped[str | None] = mapped_column(String(40))
    # the text written, None for personal data (resolved again when the .docx is built)
    rendered_text: Mapped[str | None] = mapped_column(Text)
    personal: Mapped[bool] = mapped_column(default=False)
    edited: Mapped[dict[str, Any] | None] = mapped_column()  # hand edit, for COE-01 (Phase 5)

    version: Mapped[SectionVersion] = relationship(back_populates="value_refs")
