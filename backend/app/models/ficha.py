"""Ficha-base: revisions, values, conflicts and circuits (SPEC 7.1, 7.2)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import (
    CONDUCTORS,
    INSTALLATIONS,
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
    __tablename__ = "ficha_conflict"

    value_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ficha_value.id", ondelete="CASCADE"))
    # [{"value": …, "source_type": …, "source_ref": …, "source_file_id": …, "file_date": …}]
    candidates: Mapped[list[Any]]
    resolved_value: Mapped[Any | None] = mapped_column(JSONB)
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    value: Mapped[FichaValue] = relationship(back_populates="conflicts")


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
