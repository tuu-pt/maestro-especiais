"""SQLAlchemy models (SPEC 7). Importing this package registers every table."""

from app.models.audit import AuditEvent
from app.models.document import (
    Citation,
    Document,
    DocumentRevision,
    Section,
    SectionVersion,
    ValueRef,
)
from app.models.export import Export
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
from app.models.llm import BlockedTerm, LlmCall
from app.models.profile import TechnicianProfile
from app.models.project import Project, ProjectFile
from app.models.validation import PieceFacts, ValidationIssue, ValidationRun

__all__ = [
    "ArchiveChunk",
    "ArchiveDoc",
    "AuditEvent",
    "BlockedTerm",
    "BomItem",
    "CableDesignation",
    "CableEquivalence",
    "CableOccurrence",
    "Circuit",
    "CircuitSheet",
    "Citation",
    "Document",
    "DocumentRevision",
    "Export",
    "FichaConflict",
    "FichaRevision",
    "FichaValue",
    "LlmCall",
    "PieceFacts",
    "Project",
    "ProjectFile",
    "RegulationDoc",
    "Section",
    "SectionVersion",
    "SourceDocument",
    "SourceSection",
    "TechnicianProfile",
    "TemplateBlock",
    "Typology",
    "TypologyTerm",
    "ValidationIssue",
    "ValidationRun",
    "ValueRef",
]
