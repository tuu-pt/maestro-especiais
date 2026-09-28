"""The technician's profile (SPEC 8.5): encrypted at rest, used only in the backend."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity


class TechnicianProfile(Entity):
    """Name, CC, OET/DGEG numbers… of a technician, as one encrypted JSON (Fernet).

    Never sent to the LLM (its values are blocked by the privacy guard) and never logged.
    """

    __tablename__ = "technician_profile"

    user_id: Mapped[str] = mapped_column(String(64), unique=True)
    data: Mapped[str] = mapped_column(Text)  # Fernet token of the JSON of tec.* and doc.local
