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
from app.models.enums import (
    BLOCK_MODES,
    LIBRARY_DOC_TYPES,
    REVIEW_STATUSES,
    SECTION_KINDS,
    one_of,
)
from app.models.knowledge import Reviewable


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


class TemplateBlock(Reviewable, Entity):
    """A block of the MDJ/CTE skeleton (SPEC 7.3), proposed from the reference documents.

    It never keeps project or personal data: fixed and parametric paragraphs keep their OOXML
    with {{v:<key>}}; adaptive paragraphs keep only references (archive and source sections).
    `approved_by` of the SPEC is `reviewed_by` when the status is "approved".
    """

    __tablename__ = "template_block"
    __table_args__ = (
        UniqueConstraint("doc_type", "specialty", "key", "version", name="uq_template_block_key"),
        one_of("doc_type", LIBRARY_DOC_TYPES, "ck_template_block_doc_type"),
        one_of("kind", SECTION_KINDS, "ck_template_block_kind"),
        one_of("mode", BLOCK_MODES, "ck_template_block_mode"),
        one_of("status", REVIEW_STATUSES, "ck_template_block_status"),
    )

    key: Mapped[str] = mapped_column(String(200))  # e.g. ele.mdj.dimensionamento_eletrico
    doc_type: Mapped[str] = mapped_column(String(3))
    specialty: Mapped[str] = mapped_column(String(20), default="ele")
    kind: Mapped[str] = mapped_column(String(10))  # cover | index | block | signature
    level: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    order: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10))
    activation_rule: Mapped[str | None] = mapped_column(Text)
    activation_ast: Mapped[dict[str, Any] | None] = mapped_column()
    # [{"mode", "project", "units": {"R1": [3]}, "text", "ooxml", "keys", "single_source", "note"}]
    body_template: Mapped[list[Any]] = mapped_column(default=list)
    locked_ooxml: Mapped[str | None] = mapped_column(Text)
    ooxml_rels: Mapped[dict[str, Any]] = mapped_column(default=dict)  # project -> {rId: rel}
    required_keys: Mapped[list[Any]] = mapped_column(default=list)
    equipment_slots: Mapped[list[Any]] = mapped_column(default=list)
    archive_refs: Mapped[list[Any]] = mapped_column(default=list)
    projects: Mapped[list[Any]] = mapped_column(default=list)  # where it was found
    source_refs: Mapped[list[Any]] = mapped_column(default=list)  # [{project, section_id, order}]
    notes: Mapped[list[Any]] = mapped_column(default=list)  # for the curator, in Portuguese
    version: Mapped[int] = mapped_column(Integer, default=1)


class ArchiveDoc(Entity):
    """An approved TUU document, split by block (SPEC 7.5): here, the reference MDJ/CTE."""

    __tablename__ = "archive_doc"
    __table_args__ = (one_of("doc_type", LIBRARY_DOC_TYPES, "ck_archive_doc_doc_type"),)

    project_code: Mapped[str] = mapped_column(String(32))
    doc_type: Mapped[str] = mapped_column(String(3))
    specialty: Mapped[str] = mapped_column(String(20), default="ele")
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE")
    )

    chunks: Mapped[list["ArchiveChunk"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan", order_by="ArchiveChunk.order"
    )


class ArchiveChunk(Entity):
    """Text of one block in one archived document, with the ficha values as placeholders."""

    __tablename__ = "archive_chunk"

    archive_doc_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("archive_doc.id", ondelete="CASCADE")
    )
    block_key: Mapped[str] = mapped_column(String(200))
    order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    source_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_section.id", ondelete="SET NULL")
    )

    doc: Mapped[ArchiveDoc] = relationship(back_populates="chunks")

    @property
    def ref(self) -> str:
        """How blocks and prompts cite it (SPEC 8.4): arc:<project>:<block key>."""
        return f"arc:{self.doc.project_code}:{self.block_key}"
