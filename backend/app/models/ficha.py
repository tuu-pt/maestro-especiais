"""Ficha-base: revisions, values, conflicts and circuits (SPEC 7.1, 7.2)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import (
    BOM_KINDS,
    BOM_VARIANTS,
    CONDUCTORS,
    INSTALLATIONS,
    LINK_STATUSES,
    POLE_TYPES,
    PROTECTION_TYPES,
    REVISION_STATUSES,
    SOURCE_TYPES,
    VALUE_STATUSES,
    one_of,
)


class FichaRevision(Entity):
    __tablename__ = "ficha_revision"
    __table_args__ = (
        UniqueConstraint("project_id", "label", name="uq_ficha_revision_label"),
        one_of("status", REVISION_STATUSES, "ck_ficha_revision_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(10))  # "A", "B"…
    status: Mapped[str] = mapped_column(String(20), default="draft")
    confirmed_by: Mapped[str | None] = mapped_column(String(64))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    values: Mapped[list["FichaValue"]] = relationship(
        back_populates="revision", order_by="FichaValue.key"
    )
    circuits: Mapped[list["Circuit"]] = relationship(
        back_populates="revision", order_by="Circuit.row_index"
    )
    circuit_sheets: Mapped[list["CircuitSheet"]] = relationship(
        back_populates="revision", order_by="CircuitSheet.created_at"
    )
    bom_items: Mapped[list["BomItem"]] = relationship(
        back_populates="revision", order_by="BomItem.row_index"
    )


class FichaValue(Entity):
    __tablename__ = "ficha_value"
    __table_args__ = (
        UniqueConstraint("revision_id", "key", name="uq_ficha_value_key"),
        one_of("status", VALUE_STATUSES, "ck_ficha_value_status"),
        one_of("source_type", SOURCE_TYPES, "ck_ficha_value_source_type"),
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ficha_revision.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(80))  # stable key, SPEC 7.2
    group: Mapped[str] = mapped_column(String(40))
    label_pt: Mapped[str] = mapped_column(String(160))
    value: Mapped[Any | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(20))
    personal_data: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source_type: Mapped[str] = mapped_column(String(30))
    source_ref: Mapped[str | None] = mapped_column(String(160))  # e.g. "Ficha Eletrotecnica!P29"
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_file.id", ondelete="SET NULL")
    )

    revision: Mapped[FichaRevision] = relationship(back_populates="values")
    conflicts: Mapped[list["FichaConflict"]] = relationship(back_populates="value")


class FichaConflict(Entity):
    """A divergence between sources: on a ficha value, or on one field of a circuit (09-Folha)."""

    __tablename__ = "ficha_conflict"
    __table_args__ = (
        CheckConstraint(
            "(value_id IS NOT NULL) <> (circuit_id IS NOT NULL)", name="ck_ficha_conflict_target"
        ),
        CheckConstraint("circuit_id IS NULL OR field IS NOT NULL", name="ck_ficha_conflict_field"),
    )

    value_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ficha_value.id", ondelete="CASCADE")
    )
    circuit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("circuit.id", ondelete="CASCADE")
    )
    field: Mapped[str | None] = mapped_column(String(40))  # Circuit column, e.g. "in_a"
    # [{"value": …, "source_type": …, "source_ref": …, "source_file_id": …, "file_date": …}]
    candidates: Mapped[list[Any]]
    resolved_value: Mapped[Any | None] = mapped_column(JSONB)
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    value: Mapped[FichaValue | None] = relationship(back_populates="conflicts")
    circuit: Mapped["Circuit | None"] = relationship(back_populates="conflicts")


_AMPS = Numeric(10, 2)


class Circuit(Entity):
    """One line of the Tabela de Cálculo."""

    __tablename__ = "circuit"
    __table_args__ = (
        one_of("protection_type", PROTECTION_TYPES, "ck_circuit_protection_type", nullable=True),
        one_of("pole_type", POLE_TYPES, "ck_circuit_pole_type", nullable=True),
        one_of("installation", INSTALLATIONS, "ck_circuit_installation", nullable=True),
        one_of("conductor", CONDUCTORS, "ck_circuit_conductor", nullable=True),
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ficha_revision.id", ondelete="CASCADE")
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_file.id", ondelete="SET NULL")
    )
    row_index: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(80))  # "ENTRADA DE ENERGIA", "EDIFÍCIO"
    origin: Mapped[str | None] = mapped_column(String(80))
    destination: Mapped[str | None] = mapped_column(String(80))
    kva: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    voltage_v: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    protection_type: Mapped[str | None] = mapped_column(String(2))
    ib_a: Mapped[Decimal | None] = mapped_column(_AMPS)
    in_a: Mapped[Decimal | None] = mapped_column(_AMPS)
    idn_ma: Mapped[Decimal | None] = mapped_column(_AMPS)
    iz_a: Mapped[Decimal | None] = mapped_column(_AMPS)
    i2_a: Mapped[Decimal | None] = mapped_column(_AMPS)
    iz145_a: Mapped[Decimal | None] = mapped_column(_AMPS)
    cable_raw: Mapped[str | None] = mapped_column(String(120))
    cable_normalized: Mapped[str | None] = mapped_column(String(120))
    section_mm2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))  # read from cable_raw
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    vd_section_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    vd_upstream_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    vd_total_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    breaking_capacity_ka: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pole_type: Mapped[str | None] = mapped_column(String(3))
    installation: Mapped[str | None] = mapped_column(String(3))
    phases: Mapped[int | None] = mapped_column(Integer)
    insulation: Mapped[str | None] = mapped_column(String(40))
    conductor: Mapped[str | None] = mapped_column(String(2))
    ref_method: Mapped[str | None] = mapped_column(String(20))
    rtiebt_table: Mapped[str | None] = mapped_column(String(40))
    source_ref: Mapped[str | None] = mapped_column(String(160))  # e.g. "Tabela!linha 9"

    revision: Mapped[FichaRevision] = relationship(back_populates="circuits")
    conflicts: Mapped[list[FichaConflict]] = relationship(back_populates="circuit")


class CircuitSheet(Entity):
    """One 09-Folha de Cálculo: the detail of a circuit, linked to it by rule or by a person."""

    __tablename__ = "circuit_sheet"
    __table_args__ = (one_of("link_status", LINK_STATUSES, "ck_circuit_sheet_link_status"),)

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ficha_revision.id", ondelete="CASCADE")
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_file.id", ondelete="SET NULL")
    )
    origin_hint: Mapped[str | None] = mapped_column(String(80))  # from the file name
    destination_hint: Mapped[str | None] = mapped_column(String(80))
    template: Mapped[str] = mapped_column(String(40))
    # {"in_a": {"value": 25, "ref": "proteccao!E9"}, …}
    values: Mapped[dict[str, Any]]
    # one circuit, or several equal ones (CVE 1…5); ids of this revision's circuits
    circuit_ids: Mapped[list[Any]] = mapped_column(default=list)
    link_status: Mapped[str] = mapped_column(String(10), default="unlinked")
    linked_by: Mapped[str | None] = mapped_column(String(64))
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    revision: Mapped[FichaRevision] = relationship(back_populates="circuit_sheets")


class BomItem(Entity):
    """One line of an MQT or LPU, and the ficha key it is associated with (if any)."""

    __tablename__ = "bom_item"
    __table_args__ = (
        one_of("variant", BOM_VARIANTS, "ck_bom_item_variant"),
        one_of("kind", BOM_KINDS, "ck_bom_item_kind"),
        one_of("link_status", LINK_STATUSES, "ck_bom_item_link_status"),
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ficha_revision.id", ondelete="CASCADE")
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_file.id", ondelete="SET NULL")
    )
    variant: Mapped[str] = mapped_column(String(3))
    row_index: Mapped[int] = mapped_column(Integer)
    source_ref: Mapped[str] = mapped_column(String(160))  # e.g. "MQT!linha 27"
    code: Mapped[str | None] = mapped_column(String(30))  # "8.2.1.1"
    level: Mapped[int] = mapped_column(Integer, default=0)
    parent_code: Mapped[str | None] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(12))
    designation: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    chapter_total: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    link_key: Mapped[str | None] = mapped_column(String(80))  # ficha key, SPEC 7.2
    link_status: Mapped[str] = mapped_column(String(10), default="unlinked")
    link_rule: Mapped[str | None] = mapped_column(String(40))
    linked_by: Mapped[str | None] = mapped_column(String(64))
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    revision: Mapped[FichaRevision] = relationship(back_populates="bom_items")
