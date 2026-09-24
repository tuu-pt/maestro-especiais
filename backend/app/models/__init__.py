"""SQLAlchemy models (SPEC 7). Importing this package registers every table."""

from app.models.audit import AuditEvent
from app.models.ficha import Circuit, FichaConflict, FichaRevision, FichaValue
from app.models.project import Project, ProjectFile

__all__ = [
    "AuditEvent",
    "Circuit",
    "FichaConflict",
    "FichaRevision",
    "FichaValue",
    "Project",
    "ProjectFile",
]
