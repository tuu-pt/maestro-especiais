"""SQLAlchemy models (SPEC 7). Importing this package registers every table."""

from app.models.audit import AuditEvent
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
    "FichaConflict",
    "FichaRevision",
    "FichaValue",
    "Project",
    "ProjectFile",
    "RegulationDoc",
    "SourceDocument",
    "SourceSection",
    "TemplateBlock",
    "Typology",
    "TypologyTerm",
]
