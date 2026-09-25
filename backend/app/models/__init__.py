"""SQLAlchemy models (SPEC 7). Importing this package registers every table."""

from app.models.audit import AuditEvent
from app.models.document import Citation, Document, Section, SectionVersion, ValueRef
from app.models.ficha import (
    BomItem,
    Circuit,
    CircuitSheet,
    FichaConflict,
    FichaRevision,
    FichaValue,
)
from app.models.knowledge import (
    CableDesignation,
    CableEquivalence,
    CableOccurrence,
    RegulationDoc,
    Typology,
    TypologyTerm,
)
from app.models.library import (
    ArchiveChunk,
    ArchiveDoc,
    SourceDocument,
    SourceSection,
    TemplateBlock,
)
from app.models.project import Project, ProjectFile

__all__ = [
    "ArchiveChunk",
    "ArchiveDoc",
    "AuditEvent",
    "BomItem",
    "CableDesignation",
    "CableEquivalence",
    "CableOccurrence",
    "Circuit",
    "CircuitSheet",
    "Citation",
    "Document",
    "FichaConflict",
    "FichaRevision",
    "FichaValue",
    "Project",
    "ProjectFile",
    "RegulationDoc",
    "Section",
    "SectionVersion",
    "SourceDocument",
    "SourceSection",
    "TemplateBlock",
    "Typology",
    "TypologyTerm",
    "ValueRef",
]
