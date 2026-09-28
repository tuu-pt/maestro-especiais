"""Pre-filled forms of a project (SPEC 8.5): ficha eletrotécnica, Identificação, Termo."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.assembly.assemble import confirmed_revision
from app.assembly.values import ValueSource
from app.audit import record
from app.auth import User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.forms.fill import FORMS, fill
from app.models import FichaRevision, Project
from app.profiles import revision_profile

router = APIRouter(tags=["formularios"])
DB = Annotated[Session, Depends(get_session)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]
Config = Annotated[Settings, Depends(get_settings)]


class FormOut(BaseModel):
    kind: str
    title: str
    filename: str
    by_hand: list[str]  # what the technician still fills (always the date and the signature)


def _values(db: Session, settings: Settings, project: Project) -> ValueSource:
    revision: FichaRevision | None = confirmed_revision(db, project.id)
    if revision is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A ficha-base ainda não foi confirmada: não é possível preencher os formulários.",
        )
    return ValueSource.load(db, revision, revision_profile(db, settings, revision))


def _filename(project: Project, kind: str) -> str:
    return f"{project.code or 'PROJETO'}_{FORMS[kind].suffix}"


@router.get("/projects/{project_id}/forms")
def list_forms(project_id: uuid.UUID, db: DB, settings: Config, _: Writer) -> list[FormOut]:
    project = get_project(db, project_id)
    values = _values(db, settings, project)
    return [
        FormOut(
            kind=k, title=f.title, filename=_filename(project, k), by_hand=fill(k, values).by_hand
        )
        for k, f in FORMS.items()
    ]


@router.get("/projects/{project_id}/forms/{kind}")
def download_form(
    project_id: uuid.UUID, kind: str, db: DB, settings: Config, user: Writer
) -> Response:
    if kind not in FORMS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formulário desconhecido.")
    project = get_project(db, project_id)
    filled = fill(kind, _values(db, settings, project))
    record(
        db, user, "form.downloaded", "project", project.id, {"kind": kind}, project_id=project.id
    )
    db.commit()
    name = _filename(project, kind)
    return Response(filled.data, media_type=FORMS[kind].media_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})  # fmt: skip
