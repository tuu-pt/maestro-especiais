"""Request and response bodies."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{1,31}$", examples=["MBERAL"])
    name: str = Field(min_length=1, max_length=200)
    building_type: str | None = Field(default=None, max_length=120)
    phase: Literal["licenciamento", "execucao"] = "execucao"
    public_procurement: bool = False


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    building_type: str | None
    phase: str
    specialties: list[str]
    public_procurement: bool
    status: str
    created_at: datetime
    created_by: str | None
    file_count: int = 0
    ficha_status: str | None = None  # status of the latest revision, None when there is none
    open_conflicts: int = 0


class ProjectFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    filename: str
    content_type: str | None
    size_bytes: int
    checksum: str
    template_version: str | None
    ingest_status: str
    ingest_message: str | None
    ingest_warnings: list[str]
    created_at: datetime
    created_by: str | None


class UploadOut(BaseModel):
    file: ProjectFileOut
    duplicate: bool
    job_id: str | None = None
