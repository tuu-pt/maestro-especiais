"""Block library (SPEC 7.3, 8.3): the reference MDJ/CTE split into sections, with their OOXML.

A SourceDocument is one reference document (R1, R2…); its package (styles, numbering, headers…)
is in S3. Each SourceSection keeps the body elements of one section exactly as in the document.
They are the evidence the proposed blocks come from; they are not blocks themselves.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Entity
from app.models.enums import LIBRARY_DOC_TYPES, SECTION_KINDS, one_of


class SourceDocument(Entity):
    __tablename__ = "source_document"
    __table_args__ = (one_of("doc_type", LIBRARY_DOC_TYPES, "ck_source_document_doc_type"),)

    project_code: Mapped[str] = mapped_column(String(32))  # reference project (R1, R2…)
    doc_type: Mapped[str] = mapped_column(String(3))
    specialty: Mapped[str] = mapped_column(String(20), default="ele")
    file: Mapped[str] = mapped_column(String(255))  # path inside the project folder
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    size: Mapped[int] = mapped_column(Integer)
    package_key: Mapped[str] = mapped_column(String(200))  # S3: the .docx with an empty body
    warnings: Mapped[list[Any]] = mapped_column(default=list)

    sections: Mapped[list["SourceSection"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="SourceSection.order"
    )


class SourceSection(Entity):
    __tablename__ = "source_section"
    __table_args__ = (
        UniqueConstraint("source_document_id", "order", name="uq_source_section_order"),
        one_of("kind", SECTION_KINDS, "ck_source_section_kind"),
    )

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE")
    )
    order: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))  # cover | index | block | signature
    level: Mapped[int] = mapped_column(Integer)  # 1, 2 (blocks) or 0
    key: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(200))
    ooxml: Mapped[str] = mapped_column(Text)  # the body elements, as in the document
    # {"rId5": {"type": "image", "target": "media/image1.png", "external": false, "sha256": "…"}}
    rels: Mapped[dict[str, Any]] = mapped_column(default=dict)
    text: Mapped[str] = mapped_column(Text)
    stats: Mapped[dict[str, Any]] = mapped_column(default=dict)

    document: Mapped[SourceDocument] = relationship(back_populates="sections")
