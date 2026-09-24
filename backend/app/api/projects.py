import hashlib
import mimetypes
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.ingest.detect import READABLE_KINDS, detect
from app.jobs import IngestQueue, get_publisher, get_queue
from app.models import FichaConflict, FichaRevision, FichaValue, Project, ProjectFile
from app.progress import Publish, file_event
from app.schemas import ProjectFileOut, ProjectIn, ProjectOut, UploadOut
from app.storage import ObjectStore, get_store

router = APIRouter(prefix="/projects", tags=["projetos"])

DB = Annotated[Session, Depends(get_session)]
Editor = Annotated[User, Depends(require_role("redator", "tecnico"))]


def _summary(db: Session, project: Project) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    out.file_count = (
        db.scalar(select(func.count()).where(ProjectFile.project_id == project.id)) or 0
    )
    latest = db.scalars(
        select(FichaRevision)
        .where(FichaRevision.project_id == project.id)
        .order_by(FichaRevision.created_at.desc())
        .limit(1)
    ).first()
    if latest:
        out.ficha_status = latest.status
        out.open_conflicts = (
            db.scalar(
                select(func.count())
                .select_from(FichaConflict)
                .join(FichaValue, FichaConflict.value_id == FichaValue.id)
                .where(FichaValue.revision_id == latest.id, FichaConflict.resolved_at.is_(None))
            )
            or 0
        )
    return out


def get_project(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    return project


@router.get("")
def list_projects(db: DB, _: CurrentUser) -> list[ProjectOut]:
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [_summary(db, p) for p in projects]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, db: DB, user: Editor) -> ProjectOut:
    project = Project(**body.model_dump(), created_by=user.id)
    db.add(project)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe um projeto com esse código."
        ) from None
    record(db, user, "project.created", "project", project.id, {"code": project.code},
           project_id=project.id)  # fmt: skip
    db.commit()
    return _summary(db, project)


@router.get("/{project_id}")
def read_project(project_id: uuid.UUID, db: DB, _: CurrentUser) -> ProjectOut:
    return _summary(db, get_project(db, project_id))


@router.get("/{project_id}/files")
def list_files(project_id: uuid.UUID, db: DB, _: CurrentUser) -> list[ProjectFileOut]:
    project = get_project(db, project_id)
    return [ProjectFileOut.model_validate(f) for f in project.files]


@router.post("/{project_id}/files", status_code=status.HTTP_201_CREATED)
def upload_file(
    project_id: uuid.UUID,
    db: DB,
    user: Editor,
    store: Annotated[ObjectStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    queue: Annotated[IngestQueue, Depends(get_queue)],
    publish: Annotated[Publish, Depends(get_publisher)],
    response: Response,
    upload: Annotated[UploadFile, File(alias="file")],
) -> UploadOut:
    project = get_project(db, project_id)
    data = upload.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Ficheiro demasiado grande.")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ficheiro vazio.")
    filename = (upload.filename or "ficheiro").replace("\\", "/").rsplit("/", 1)[-1][:255]
    checksum = hashlib.sha256(data).hexdigest()

    existing = db.scalars(
        select(ProjectFile).where(
            ProjectFile.project_id == project.id, ProjectFile.checksum == checksum
        )
    ).first()
    if existing:
        response.status_code = status.HTTP_200_OK
        return UploadOut(file=ProjectFileOut.model_validate(existing), duplicate=True)

    found = detect(filename, data)
    file_id = uuid.uuid4()
    content_type = upload.content_type or mimetypes.guess_type(filename)[0]
    file = ProjectFile(
        id=file_id,
        project_id=project.id,
        kind=found.kind,
        filename=filename,
        storage_key=f"projects/{project.id}/files/{file_id}",
        content_type=content_type,
        size_bytes=len(data),
        checksum=checksum,
        template_version=found.template_version,
        ingest_status="pending" if found.kind in READABLE_KINDS else "skipped",
        ingest_message=found.note
        or (None if found.kind in READABLE_KINDS else "Leitura deste tipo na Fase 2."),
        created_by=user.id,
    )
    store.put(file.storage_key, data, content_type)
    db.add(file)
    # The name may hold personal data: the audit keeps kind, size and checksum only.
    record(
        db,
        user,
        "file.uploaded",
        "project_file",
        file.id,
        {"kind": file.kind, "size": len(data), "sha256": checksum},
        project_id=project.id,
    )
    db.commit()
    job_id = None
    if file.ingest_status == "pending":
        job_id = queue.enqueue(file.id)
        if job_id is None:
            file.ingest_message = "Fila de leitura indisponível: tente carregar de novo mais tarde."
            db.commit()
        else:
            response.status_code = status.HTTP_202_ACCEPTED
    publish(project.id, file_event(file, "Ficheiro carregado"))
    return UploadOut(file=ProjectFileOut.model_validate(file), duplicate=False, job_id=job_id)
