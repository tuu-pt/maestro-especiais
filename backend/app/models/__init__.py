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
from app.models.equipment import (
    Datasheet,
    Equipment,
    EquipmentParam,
    ProjectEquipment,
    Requirement,
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
from app.models.pilot import PilotBaseline, PilotNote, PilotTime
from app.models.profile import TechnicianProfile
from app.models.project import Project, ProjectFile
from app.models.setting import AppSetting
from app.models.user import AppUser
from app.models.validation import PieceFacts, ValidationIssue, ValidationRun

__all__ = [
    "AppSetting",
    "AppUser",
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
    "Datasheet",
    "Document",
    "DocumentRevision",
    "Equipment",
    "EquipmentParam",
    "Export",
    "FichaConflict",
    "FichaRevision",
    "FichaValue",
    "LlmCall",
    "PieceFacts",
    "PilotBaseline",
    "PilotNote",
    "PilotTime",
    "Project",
    "ProjectEquipment",
    "ProjectFile",
    "RegulationDoc",
    "Requirement",
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
