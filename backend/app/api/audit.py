"""Audit timeline of a project and recent activity (SPEC P7, screens A and H)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth import DEV_USERS, CurrentUser
from app.db import get_session
from app.ingest.keys import KEYS
from app.models import AuditEvent, Project

router = APIRouter(tags=["auditoria"])

DB = Annotated[Session, Depends(get_session)]

KIND_LABELS_PT = {
    "ficha_eletrotecnica": "ficha eletrotécnica",
    "calc_summary": "Tabela de Cálculo",
    "calc_circuit": "09-Folha de Cálculo",
    "mqt": "mapa de quantidades",
    "lpu": "lista de preços unitários",
    "drawing_pdf": "peças desenhadas (PDF)",
    "drawing_dwg": "peças desenhadas (DWG)",
    "archive_docx": "documento",
    "other": "ficheiro",
}
KNOWLEDGE_LABELS_PT = {
    "cable-designations": "a designação de cabo",
    "cable-equivalences": "a equivalência de cabos",
    "typologies": "a tipologia",
    "typology-terms": "o termo incompatível",
}
_NAMES = {u.id: u.name for u in DEV_USERS.values()}


class AuditOut(BaseModel):
    id: uuid.UUID
    at: datetime
    actor_type: str
    actor_name: str
    action: str
    description: str
    project_id: str | None
    project_code: str | None


def describe(action: str, payload: dict[str, Any]) -> str:
    """A sentence for people. Payloads never hold personal values, so neither does this."""
    kind = KIND_LABELS_PT.get(str(payload.get("kind")), "ficheiro")
    key = KEYS.get(str(payload.get("key")))
    label = key.label_pt if key else "valor"
    match action:
        case "project.created":
            return f"Projeto {payload.get('code', '')} criado"
        case "file.uploaded":
            return f"Carregou {kind}"
        case "file.ingested":
            return f"Leu {kind}: {payload.get('summary', '')}".rstrip(": ")
        case "file.ingest_failed":
            return f"Não conseguiu ler {kind}"
        case "ficha.value_revealed":
            return f"Revelou o dado pessoal «{label}»"
        case "ficha.conflict_resolved":
            how = "valor manual" if payload.get("choice") == "manual" else "candidato escolhido"
            return f"Resolveu o conflito «{label}» ({how})"
        case "ficha.circuit_conflict_resolved":
            how = "valor manual" if payload.get("choice") == "manual" else "candidato escolhido"
            return f"Resolveu o conflito do troço {payload.get('circuit', '')} ({how})"
        case "bom_item.linked":
            target = KEYS.get(str(payload.get("link_key")))
            art = f"artigo {payload.get('code') or ''}".strip()
            if target:
                return f"Associou o {art} a «{target.label_pt}»"
            return f"Retirou a associação do {art}"
        case "circuit_sheet.linked":
            n = int(payload.get("circuits") or 0)
            where = f"a {n} troço{'s' if n != 1 else ''}" if n else "sem troço"
            return f"Associou a 09-Folha {payload.get('sheet', '')} {where}"
        case "knowledge.approved" | "knowledge.rejected":
            verb = "Aprovou" if action == "knowledge.approved" else "Rejeitou"
            what = KNOWLEDGE_LABELS_PT.get(str(payload.get("kind")), "o elemento")
            return f"{verb} {what} «{payload.get('label', '')}»"
        case "ficha.confirmed":
            return f"Confirmou a ficha-base rev. {payload.get('label', '')}"
    return action


def _out(event: AuditEvent, codes: dict[str, str]) -> AuditOut:
    project_id = event.payload.get("project_id")
    return AuditOut(
        id=event.id,
        at=event.at,
        actor_type=event.actor_type,
        actor_name=_NAMES.get(event.actor_id or "", "Sistema")
        if event.actor_type == "user"
        else "Sistema",
        action=event.action,
        description=describe(event.action, event.payload),
        project_id=project_id,
        project_code=codes.get(str(project_id)),
    )


def _codes(db: Session) -> dict[str, str]:
    return {str(i): code for i, code in db.execute(select(Project.id, Project.code))}


@router.get("/projects/{project_id}/audit")
def project_audit(project_id: uuid.UUID, db: DB, _: CurrentUser) -> list[AuditOut]:
    project = get_project(db, project_id)
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.payload["project_id"].astext == str(project.id))
        .order_by(AuditEvent.at, AuditEvent.id)
    ).all()
    codes = {str(project.id): project.code}
    return [_out(e, codes) for e in events]


@router.get("/activity")
def activity(
    db: DB, _: CurrentUser, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[AuditOut]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.at.desc()).limit(limit)).all()
    codes = _codes(db)
    return [_out(e, codes) for e in events]
