"""Exports of a project (Phase 6): ask for a draft or the official set, list them, download them,
and the endpoint for TUU Maestro (D9) with links signed by the API."""

import hashlib
import hmac
import time
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.api.review import user_name
from app.audit import record
from app.auth import User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.export import ExportRefused
from app.export.bundle import ZIP, queue_export
from app.export.jobs import ExportQueue, get_export_queue
from app.models import Export, Project
from app.storage import ObjectStore, get_store

router = APIRouter(tags=["exportação"])
DB = Annotated[Session, Depends(get_session)]
Store = Annotated[ObjectStore, Depends(get_store)]
Config = Annotated[Settings, Depends(get_settings)]
Queue = Annotated[ExportQueue, Depends(get_export_queue)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]
Reader = Annotated[User, Depends(require_role("redator", "tecnico", "admin"))]


class ExportIn(BaseModel):
    kind: Literal["draft", "official"]
    pdf: bool = False


class ExportOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    message: str | None
    version: str
    with_pdf: bool
    zip_name: str | None
    zip_size: int | None
    zip_sha256: str | None
    files: list[dict[str, Any]]
    created_at: datetime
    created_by_name: str | None
    finished_at: datetime | None


def _out(db: Session, e: Export) -> ExportOut:
    files = [{k: f.get(k) for k in ("name", "piece", "revision", "sha256", "size", "by_hand")}
             for f in e.files]  # fmt: skip
    return ExportOut(
        id=e.id, kind=e.kind, status=e.status, message=e.message, version=e.version,
        with_pdf=e.with_pdf, zip_name=e.zip_name, zip_size=e.zip_size, zip_sha256=e.zip_sha256,
        files=files, created_at=e.created_at, created_by_name=user_name(db, e.created_by),
        finished_at=e.finished_at,
    )  # fmt: skip


def _export(db: Session, export_id: uuid.UUID) -> Export:
    export = db.get(Export, export_id)
    if export is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exportação não encontrada.")
    return export


@router.post("/projects/{project_id}/exports", status_code=status.HTTP_202_ACCEPTED)
def create_export(project_id: uuid.UUID, body: ExportIn, db: DB, queue: Queue, user: Writer
                  ) -> ExportOut:  # fmt: skip
    project = get_project(db, project_id)
    if body.kind == "official" and "tecnico" not in user.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só um técnico exporta o conjunto oficial.")
    try:
        export = queue_export(db, project, body.kind, body.pdf, user.id)
    except ExportRefused as exc:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            {"message": "Ainda não é possível exportar o conjunto oficial.",
                             "reasons": exc.reasons}) from exc  # fmt: skip
    record(db, user, "export.requested", "export", export.id,
           {"kind": body.kind, "pdf": body.pdf, "version": export.version},
           project_id=project.id)  # fmt: skip
    db.commit()
    if queue.enqueue(export.id) is None:
        export.status, export.message = "failed", "A fila de exportação não está disponível."
        db.commit()
    db.refresh(export)
    return _out(db, export)


@router.get("/projects/{project_id}/exports")
def list_exports(project_id: uuid.UUID, db: DB, _: Reader) -> list[ExportOut]:
    project = get_project(db, project_id)
    rows = db.scalars(select(Export).where(Export.project_id == project.id)
                      .order_by(Export.created_at.desc()))  # fmt: skip
    return [_out(db, e) for e in rows]


@router.get("/exports/{export_id}")
def read_export(export_id: uuid.UUID, db: DB, _: Reader) -> ExportOut:
    return _out(db, _export(db, export_id))


def _can_download(user: User, export: Export) -> None:
    allowed = ("redator", "tecnico") if export.kind == "draft" else ("redator", "tecnico", "admin")
    if not user.has_any(allowed):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "O seu papel não descarrega esta exportação."
        )


def _attachment(data: bytes, name: str, media_type: str) -> Response:
    disposition = f"attachment; filename*=UTF-8''{quote(name)}"
    return Response(data, media_type=media_type, headers={"Content-Disposition": disposition})


def _download(db: Session, store: ObjectStore, export: Export, name: str | None,
              actor: User | None, via: str) -> Response:  # fmt: skip
    if export.status != "done" or not export.zip_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "A exportação ainda não está pronta.")
    if name is None:
        data, filename, media_type = (
            store.get(export.zip_key),
            export.zip_name or "conjunto.zip",
            ZIP,
        )
    else:
        found = next((f for f in export.files if f["name"] == name), None)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ficheiro inexistente nesta exportação.")
        data, filename, media_type = store.get(found["key"]), name, found["media_type"]
    record(db, actor, "export.downloaded", "export", export.id,
           {"kind": export.kind, "file": filename, "via": via}, project_id=export.project_id,
           actor_type="user" if actor else "system")  # fmt: skip
    db.commit()
    return _attachment(data, filename, media_type)


@router.get("/exports/{export_id}/bundle.zip")
def download_bundle(export_id: uuid.UUID, db: DB, store: Store, user: Reader) -> Response:
    export = _export(db, export_id)
    _can_download(user, export)
    return _download(db, store, export, None, user, "aplicação")


# ---------------------------------------------------------------- links signed by the API (D9)


def sign(settings: Settings, export_id: uuid.UUID, name: str, expires: int) -> str:
    message = f"{export_id}|{name}|{expires}".encode()
    return hmac.new(settings.export_link_secret.encode(), message, hashlib.sha256).hexdigest()


def signed_link(request: Request, settings: Settings, export: Export, name: str | None) -> str:
    expires = int(time.time()) + settings.export_link_ttl_s
    target = name or "bundle.zip"
    token = sign(settings, export.id, target, expires)
    base = str(request.base_url).rstrip("/")
    return (f"{base}/api/exports/{export.id}/signed/{quote(target)}"
            f"?expires={expires}&token={token}")  # fmt: skip


@router.get("/exports/{export_id}/signed/{name}")
def download_signed(export_id: uuid.UUID, name: str, expires: int, token: str, db: DB,
                    store: Store, settings: Config) -> Response:  # fmt: skip
    """A file of an official export through a link signed by the API: no login, 24 h."""
    if not settings.export_link_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Links assinados não configurados."
        )
    expected = sign(settings, export_id, name, expires)
    if expires < time.time() or not hmac.compare_digest(expected, token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Link inválido ou expirado.")
    export = _export(db, export_id)
    if export.kind != "official":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o conjunto oficial tem links assinados.")
    return _download(db, store, export, None if name == "bundle.zip" else name, None, "link")


@router.get("/integration/projects/{code}/export")
def tuu_maestro(
    code: str, request: Request, db: DB, settings: Config,
    x_service_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:  # fmt: skip
    """D9: the last official set of a project, for TUU Maestro: its manifest and signed links."""
    if not settings.maestro_service_token or not settings.export_link_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Integração com o TUU Maestro não configurada.")  # fmt: skip
    if not x_service_token or not hmac.compare_digest(
        x_service_token, settings.maestro_service_token
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de serviço inválido.")
    project = db.scalars(select(Project).where(Project.code == code)).first()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
    export = db.scalars(select(Export).where(Export.project_id == project.id,
                                             Export.kind == "official", Export.status == "done")
                        .order_by(Export.created_at.desc())).first()  # fmt: skip
    if export is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "O projeto ainda não tem conjunto oficial.")
    record(db, None, "export.integration_read", "export", export.id, {"version": export.version},
           project_id=project.id, actor_type="system")  # fmt: skip
    db.commit()
    return {
        "projeto": project.code,
        "versao": export.version,
        "exportado_em": export.finished_at.isoformat() if export.finished_at else None,
        "manifesto": export.manifest,
        "conjunto": {"nome": export.zip_name, "sha256": export.zip_sha256,
                     "link": signed_link(request, settings, export, None)},
        "ficheiros": [{"nome": f["name"], "sha256": f["sha256"],
                       "link": signed_link(request, settings, export, f["name"])}
                      for f in export.files],
        "links_validos_ate": int(time.time()) + settings.export_link_ttl_s,
    }  # fmt: skip
