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
    Typology,
    TypologyTerm,
)
from app.models.library import SourceDocument, SourceSection
from app.models.project import Project, ProjectFile

__all__ = [
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
    "SourceDocument",
    "SourceSection",
    "Typology",
    "TypologyTerm",
]
