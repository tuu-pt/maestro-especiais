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
STATUS_PT = {"in_force": "em vigor", "revoked": "revogado", "reference_only": "só referência"}
EDIT_LABELS_PT = {"title": "título", "mode": "modo", "activation_rule": "regra de ativação"}
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
        case "knowledge.regulation_confirmed":
            legal = STATUS_PT.get(str(payload.get("status")), "")
            return f"Confirmou «{payload.get('label', '')}» ({legal})"
        case "knowledge.regulation_rejected":
            return f"Rejeitou «{payload.get('label', '')}» do corpus"
        case "knowledge.regulation_citable":
            verb = "Marcou" if payload.get("citable") else "Desmarcou"
            return f"{verb} «{payload.get('label', '')}» como citável"
        case "library.block_approved" | "library.block_rejected":
            verb = "Aprovou" if action.endswith("approved") else "Rejeitou"
            return f"{verb} o bloco «{payload.get('title', '')}» ({payload.get('doc_type', '')})"
        case "library.block_edited":
            what = ", ".join(EDIT_LABELS_PT.get(k, k) for k in payload.get("changed") or {})
            return f"Editou o bloco «{payload.get('title', '')}»: {what}"
        case "document.assembled":
            return f"Montou o {payload.get('type', '')} ({payload.get('sections', 0)} secções)"
        case "document.generation_requested":
            n = payload.get("sections", 0)
            return f"Pediu a redação do {payload.get('type', '')} ({n} secções)"
        case "section.generation_requested":
            return f"Pediu a redação de «{payload.get('title', '')}»"
        case "section.request":
            return f"Pediu uma alteração ao agente em «{payload.get('title', '')}»"
        case "section.draft_proposed":
            return f"Propôs a versão {payload.get('version', '')} de «{payload.get('title', '')}»"
        case "section.version_accepted":
            return f"Aceitou a versão {payload.get('version', '')} de «{payload.get('title', '')}»"
        case "section.version_rejected":
            return f"Rejeitou a versão {payload.get('version', '')} de «{payload.get('title', '')}»"
        case "section.unlocked":
            reason = payload.get("reason", "")
            return f"Desbloqueou o bloco fixo «{payload.get('title', '')}»: {reason}"
        case "section.activated" | "section.deactivated":
            verb = "Ativou" if action == "section.activated" else "Desativou"
            return f"{verb} «{payload.get('title', '')}»: {payload.get('reason', '')}"
        case "section.reviewed":
            return f"Marcou «{payload.get('title', '')}» como revista"
        case "section.edited":
            extra = " (valores da ficha alterados)" if payload.get("values_changed") else ""
            return f"Editou «{payload.get('title', '')}»{extra}"
        case "llm.refused":
            return "Pedido ao LLM recusado: LLM desligado neste projeto"
        case "settings.llm_primary":
            to, why = payload.get("to", ""), payload.get("reason", "")
            return f"Mudou o LLM principal para {to}: {why}"
        case "project.llm_allowed":
            return "Permitiu o uso do LLM" if payload.get("allowed") else "Retirou o uso do LLM"
        case "form.downloaded":
            titles = {"ficha_eletrotecnica": "a ficha eletrotécnica",
                      "identificacao": "a Identificação do Projeto",
                      "termo": "o Termo de Responsabilidade"}  # fmt: skip
            title = titles.get(payload.get("kind", ""), "um formulário")
            return f"Descarregou {title} pré-preenchido"
        case "profile.updated":
            return "Atualizou o perfil de técnico"
        case "export.requested":
            kind = "o conjunto oficial" if payload.get("kind") == "official" else "um rascunho"
            return f"Pediu a exportação de {kind} ({payload.get('version', '')})"
        case "export.done":
            kind = "Conjunto oficial" if payload.get("kind") == "official" else "Rascunho"
            files, version = payload.get("files", 0), payload.get("version", "")
            return f"{kind} exportado ({files} ficheiros, {version})"
        case "export.failed":
            return "A exportação falhou"
        case "export.downloaded":
            via = " por link assinado" if payload.get("via") == "link" else ""
            return f"Descarregou {payload.get('file', 'a exportação')}{via}"
        case "export.integration_read":
            return f"O TUU Maestro leu o conjunto oficial ({payload.get('version', '')})"
        case "document.approved":
            return f"Aprovou o {payload.get('type', '')} (rev. {payload.get('revision', '')})"
        case "document.reopened":
            return (f"Reabriu o {payload.get('type', '')}: rev. {payload.get('from', '')} → "
                    f"rev. {payload.get('to', '')} ({payload.get('reason', '')})")  # fmt: skip
        case "document.responsible_assigned":
            return f"Atribuiu o técnico responsável do {payload.get('type', '')}"
        case "document.header_date":
            what = "Escreveu" if payload.get("set") else "Apagou"
            return f"{what} a data do cabeçalho do {payload.get('type', '')}"
        case "document.draft_downloaded":
            return f"Descarregou o rascunho do {payload.get('type', '')}"
        case "ficha.manual_value":
            return f"Acrescentou à mão o valor «{label}» (rev. {payload.get('revision', '')})"
        case "ficha.confirmed":
            return f"Confirmou a ficha-base rev. {payload.get('label', '')}"
        case "validation.requested":
            what = "a revalidação" if payload.get("trigger") == "changed" else "a validação"
            return f"Pediu {what} do projeto"
        case "validation.run":
            n = payload.get("critical", 0)
            return (
                f"Validou o projeto: {n} crítico{'s' if n != 1 else ''}, "
                f"{payload.get('warning', 0)} avisos, {payload.get('info', 0)} informações"
            )
        case "validation.issue_ignored":
            return f"Ignorou um alerta {payload.get('rule', '')}: {payload.get('reason', '')}"
        case "validation.issue_reopened":
            return f"Reabriu um alerta {payload.get('rule', '')}"
        case "review.requested":
            n = payload.get("documents", 0)
            return f"Enviou {n} peça{'s' if n != 1 else ''} para revisão"
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
