"""Knowledge base (SPEC 7.5): cable dictionary and typology lexicon.

Everything the agent seeds is "proposed". Only a curator approves or rejects (SPEC 4, 10.G).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import (
    REGULATION_KINDS,
    REGULATION_REVIEW,
    REGULATION_STATUSES,
    REVIEW_STATUSES,
    one_of,
)


class Reviewable:
    """Columns of what a curator reviews."""

    status: Mapped[str] = mapped_column(String(10), default="proposed")
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class CableDesignation(Reviewable, Entity):
    """A cable or wire family, e.g. "XZ1(frt,zh)". Aliases are the equivalences approved."""

    __tablename__ = "cable_designation"
    __table_args__ = (one_of("status", REVIEW_STATUSES, "ck_cable_designation_status"),)

    canonical: Mapped[str] = mapped_column(String(60), unique=True)
    aliases: Mapped[list[Any]] = mapped_column(default=list)
    kind: Mapped[str] = mapped_column(String(5))  # fio | cabo
    flexible: Mapped[bool | None]
    fire_class_default: Mapped[str | None] = mapped_column(String(20))

    occurrences: Mapped[list["CableOccurrence"]] = relationship(
        back_populates="designation",
        cascade="all, delete-orphan",
        order_by="CableOccurrence.project_code",
    )


class CableOccurrence(Entity):
    """Where a designation appears, written exactly as there."""

    __tablename__ = "cable_occurrence"

    designation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cable_designation.id", ondelete="CASCADE")
    )
    project_code: Mapped[str] = mapped_column(String(32))  # reference project (R1, R2…)
    source: Mapped[str] = mapped_column(String(20))  # Tabela, 09-Folha, MQT, LPU, MDJ, CTE
    source_file: Mapped[str] = mapped_column(String(255))
    locator: Mapped[str] = mapped_column(String(120))  # cell, line or paragraph
    raw_text: Mapped[str] = mapped_column(String(160))
    geometry: Mapped[str | None] = mapped_column(String(30))

    designation: Mapped[CableDesignation] = relationship(back_populates="occurrences")


class CableEquivalence(Reviewable, Entity):
    """A proposed equivalence between two families, with the evidence that suggested it."""

    __tablename__ = "cable_equivalence"
    __table_args__ = (
        UniqueConstraint("a_id", "b_id", name="uq_cable_equivalence_pair"),
        one_of("status", REVIEW_STATUSES, "ck_cable_equivalence_status"),
    )

    a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cable_designation.id", ondelete="CASCADE"))
    b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cable_designation.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text)
    # [{"project": "R2", "geometry": "5G10", "a": {...occurrence}, "b": {...occurrence}}]
    evidence: Mapped[list[Any]] = mapped_column(default=list)

    a: Mapped[CableDesignation] = relationship(foreign_keys=[a_id])
    b: Mapped[CableDesignation] = relationship(foreign_keys=[b_id])


class Typology(Reviewable, Entity):
    """A building typology found in the reference projects, e.g. "moradia unifamiliar"."""

    __tablename__ = "typology"
    __table_args__ = (one_of("status", REVIEW_STATUSES, "ck_typology_status"),)

    name: Mapped[str] = mapped_column(String(120), unique=True)
    # [{"project": "R1", "source": "Ficha eletrotécnica", "locator": "F23", "text": "Unifamiliar"}]
    evidence: Mapped[list[Any]] = mapped_column(default=list)

    terms: Mapped[list["TypologyTerm"]] = relationship(
        back_populates="typology", cascade="all, delete-orphan", order_by="TypologyTerm.term"
    )


class TypologyTerm(Reviewable, Entity):
    """A term that should not appear in the documents of a typology (rule TIP-01)."""

    __tablename__ = "typology_term"
    __table_args__ = (
        UniqueConstraint("typology_id", "term", name="uq_typology_term"),
        one_of("status", REVIEW_STATUSES, "ck_typology_term_status"),
    )

    typology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("typology.id", ondelete="CASCADE"))
    term: Mapped[str] = mapped_column(String(80))
    relation: Mapped[str] = mapped_column(String(20), default="incompatible")
    # where the term was found in documents of this typology (e.g. case C2)
    evidence: Mapped[list[Any]] = mapped_column(default=list)

    typology: Mapped[Typology] = relationship(back_populates="terms")


class RegulationDoc(Entity):
    """A diploma, guide or standard of the corpus (SPEC 7.5): a reference, never its full text.

    `status` is the legal status the curator confirms; `citable` stays false until then (only
    citable documents are cited, P6). Standards under copyright keep only title and scope.
    """

    __tablename__ = "regulation_doc"
    __table_args__ = (
        one_of("status", REGULATION_STATUSES, "ck_regulation_doc_status", nullable=True),
        one_of("review_status", REGULATION_REVIEW, "ck_regulation_doc_review_status"),
        one_of("kind", REGULATION_KINDS, "ck_regulation_doc_kind"),
    )

    code: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(15))
    edition: Mapped[str | None] = mapped_column(String(80))
    issuer: Mapped[str | None] = mapped_column(String(80))
    scope: Mapped[str] = mapped_column(String(300))  # âmbito, one sentence
    specialties: Mapped[list[Any]] = mapped_column(default=list)
    status: Mapped[str | None] = mapped_column(String(15))
    citable: Mapped[bool] = mapped_column(default=False)
    copyrighted: Mapped[bool] = mapped_column(default=False)
    license_note: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str] = mapped_column(String(10), default="proposed")
    reviewed_by: Mapped[str | None] = mapped_column(String(64))  # the curator (curator_id)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    # where the reference projects cite it: [{project, source, file, locator, text}]
    found_in: Mapped[list[Any]] = mapped_column(default=list)
    found_count: Mapped[int] = mapped_column(Integer, default=0)
