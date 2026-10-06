"""Equipment library of TUU (SPEC 7.6, Phase 7).

An Equipment is a reference item of the CTE (a portinhola, a luminaire type, an inverter…):
seeded from the reference CTEs as "proposed", reviewed by a curator. Its datasheets are files in
S3; their parameters are read by patterns ("extracted") and confirmed by a curator ("reviewed").
A Requirement is what a CTE block asks of its equipment, read from the block's text. A
ProjectEquipment is the equipment of one slot of an assembled CTE section. Nothing here is a
person's data: manufacturers, models and their characteristics only.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import REVIEW_STATUSES, one_of
from app.models.knowledge import Reviewable

PARAM_ORIGINS = ("cte", "datasheet")
PARAM_REVIEW = ("extracted", "reviewed")
DATASHEET_STATUSES = ("current", "outdated")
REQUIREMENT_OPERATORS = (">=", "<=", "=", ">=class", "info")


class Equipment(Reviewable, Entity):
    __tablename__ = "equipment"
    __table_args__ = (one_of("status", REVIEW_STATUSES, "ck_equipment_status"),)

    identity: Mapped[str] = mapped_column(String(300), unique=True)  # folded maker + model/ref
    category: Mapped[str] = mapped_column(String(30))  # app.equipment.categories
    name: Mapped[str] = mapped_column(String(300))  # as the CTE describes it
    manufacturer: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(10))  # luminaire type: L1, SNC…
    specialties: Mapped[list[Any]] = mapped_column(default=lambda: ["ele"])
    or_equivalent: Mapped[bool] = mapped_column(default=True)  # the CTE said "ou equivalente"
    # where the CTE names it: [{"project", "block_key", "entry", "section_id", "unit", "text"}]
    sources: Mapped[list[Any]] = mapped_column(default=list)
    # the illustration of the CTE: {"project", "block_key", "entry"} of an image entry
    image: Mapped[dict[str, Any] | None] = mapped_column()

    params: Mapped[list["EquipmentParam"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan", order_by="EquipmentParam.name"
    )
    datasheets: Mapped[list["Datasheet"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan",
        order_by="Datasheet.created_at.desc()",
    )  # fmt: skip


class Datasheet(Entity):
    __tablename__ = "datasheet"
    __table_args__ = (
        UniqueConstraint("equipment_id", "sha256", name="uq_datasheet_sha256"),
        one_of("status", DATASHEET_STATUSES, "ck_datasheet_status"),
    )

    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(200))  # equipment/<id>/datasheets/<uuid>
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    issue_date: Mapped[date | None] = mapped_column(Date)
    issue_date_text: Mapped[str | None] = mapped_column(String(60))  # as read, for the curator
    language: Mapped[str | None] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(10), default="current")
    warnings: Mapped[list[Any]] = mapped_column(default=list)

    equipment: Mapped[Equipment] = relationship(back_populates="datasheets")


class EquipmentParam(Entity):
    __tablename__ = "equipment_param"
    __table_args__ = (
        one_of("origin", PARAM_ORIGINS, "ck_equipment_param_origin"),
        one_of("review_status", PARAM_REVIEW, "ck_equipment_param_review"),
    )

    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"))
    datasheet_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("datasheet.id", ondelete="CASCADE")
    )
    origin: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(40))  # app.equipment.params.PARAMS
    value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str] = mapped_column(String(10), default="")
    text: Mapped[str] = mapped_column(Text, default="")  # what was read, as written
    page: Mapped[int | None] = mapped_column(Integer)
    review_status: Mapped[str] = mapped_column(String(10), default="extracted")
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    equipment: Mapped[Equipment] = relationship(back_populates="params")


class Requirement(Reviewable, Entity):
    """What a CTE block asks; `equipment_id` None: of every equipment of the block."""

    __tablename__ = "equipment_requirement"
    __table_args__ = (
        one_of("operator", REQUIREMENT_OPERATORS, "ck_equipment_requirement_operator"),
        one_of("status", REVIEW_STATUSES, "ck_equipment_requirement_status"),
    )

    doc_type: Mapped[str] = mapped_column(String(3), default="CTE")
    block_key: Mapped[str] = mapped_column(String(200))
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(30))
    param_name: Mapped[str] = mapped_column(String(40))
    operator: Mapped[str] = mapped_column(String(8))
    value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str] = mapped_column(String(10), default="")
    # evidence: [{"project", "section_id", "unit", "text"}] (the line of the CTE, masked)
    sources: Mapped[list[Any]] = mapped_column(default=list)


class ProjectEquipment(Entity):
    """The equipment of one slot (a block entry) of an assembled CTE section."""

    __tablename__ = "project_equipment"
    __table_args__ = (UniqueConstraint("section_id", "entry", name="uq_project_equipment_slot"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("section.id", ondelete="CASCADE"))
    entry: Mapped[int] = mapped_column(Integer)  # the block entry that names the equipment
    block_key: Mapped[str] = mapped_column(String(200))
    default_equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL")
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL")
    )
    or_equivalent: Mapped[bool] = mapped_column(default=True)
    ficha_key: Mapped[str | None] = mapped_column(String(80))  # eq.portinhola, eq.luminarias…
    chosen_by: Mapped[str | None] = mapped_column(String(64))  # set when a person chose it
    chosen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)

    equipment: Mapped[Equipment | None] = relationship(foreign_keys=[equipment_id])
