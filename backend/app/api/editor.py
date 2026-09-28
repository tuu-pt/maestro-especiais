"""Actions of the assisted editor (screen D), each one a person's action, audited.

- a fixed block is locked: editing it needs an unlock with a reason;
- a section the rule did not activate can be activated (or the other way) with a reason;
- a hand edit is a new version by the user; changing a value that came from a placeholder needs
  a confirmation and is marked for COE-01 (Phase 5);
- "marcar como revista" ends the highlight of the generated text.
"""

import copy
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record
from app.auth import User, require_role
from app.db import get_session
from app.models import Section, SectionVersion, ValueRef
from app.validation.jobs import ValidationQueue, get_validation_queue, revalidate

router = APIRouter(tags=["editor"])

DB = Annotated[Session, Depends(get_session)]
Writer = Annotated[User, Depends(require_role("redator", "tecnico"))]
Revalidation = Annotated[ValidationQueue, Depends(get_validation_queue)]
PROTECTED = "Bloco fixo protegido: desbloqueie com justificação para o editar."


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class ActivationIn(ReasonIn):
    active: bool


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ContentIn(BaseModel):
    content: dict[str, Any]
    confirm_values: bool = False  # the person confirmed changing values from placeholders
    note: str | None = Field(default=None, max_length=2000)


def _section(db: Session, section_id: uuid.UUID) -> Section:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secção não encontrada.")
    return section


READ_ONLY = (
    "Peça existente, carregada para auditoria: só leitura. Corrija o original e carregue-o de novo."
)


def _writable(db: Session, section_id: uuid.UUID) -> Section:
    section = _section(db, section_id)
    if section.document.origin == "existing":
        raise HTTPException(status.HTTP_409_CONFLICT, READ_ONLY)
    return section


def _now(user: User, reason: str) -> dict[str, Any]:
    return {"by": user.id, "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "reason": reason.strip()}  # fmt: skip


def _audit(db: Session, user: User, action: str, section: Section, **payload: Any) -> None:
    record(db, user, action, "section", section.id, {"title": section.title, **payload},
           project_id=section.document.project_id)  # fmt: skip


@router.post("/sections/{section_id}/unlock")
def unlock(section_id: uuid.UUID, body: ReasonIn, db: DB, user: Writer) -> dict[str, Any]:
    section = _writable(db, section_id)
    if not section.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta secção não está protegida.")
    section.unlocked = _now(user, body.reason)
    _audit(db, user, "section.unlocked", section, reason=body.reason.strip())
    db.commit()
    return {"unlocked": section.unlocked}


@router.post("/sections/{section_id}/activation")
def activation(section_id: uuid.UUID, body: ActivationIn, db: DB, user: Writer) -> dict[str, Any]:
    section = _writable(db, section_id)
    if section.active == body.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "A secção já está nesse estado.")
    section.activation_override = {**_now(user, body.reason), "active": body.active,
                                   "rule_result": section.active}  # fmt: skip
    section.active = body.active
    _audit(db, user, "section.activated" if body.active else "section.deactivated", section,
           reason=body.reason.strip())  # fmt: skip
    db.commit()
    return {"active": section.active, "activation_override": section.activation_override}


@router.post("/sections/{section_id}/review")
def review(section_id: uuid.UUID, body: ReviewIn, db: DB, user: Writer) -> dict[str, Any]:
    section = _section(db, section_id)
    note = section.status_note or ""
    if section.missing_keys and section.status == "todo" and note.startswith("Falta dado"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Não pode ser revista: {note}")
    if any(n.get("type") == "pending" for n in _current(section).content.get("content") or []):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Não pode ser revista: falta o texto adaptativo.")  # fmt: skip
    section.status, section.status_note = "reviewed", None
    section.reviewed_by, section.reviewed_at = user.id, datetime.now(UTC)
    _audit(db, user, "section.reviewed", section, note=body.note)
    db.commit()
    return {"status": section.status, "reviewed_by": section.reviewed_by}


def _current(section: Section) -> SectionVersion:
    return next(v for v in section.versions if v.number == section.current_version)


def _locked_nodes(content: dict[str, Any]) -> list[Any]:
    return [n for n in content.get("content") or [] if n.get("type") == "locked"]


def _value_marks(content: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """anchor -> (text, attrs) of every value in the content."""
    out: dict[str, tuple[str, dict[str, Any]]] = {}

    def walk(node: dict[str, Any]) -> None:
        for mark in node.get("marks") or []:
            if mark.get("type") == "value":
                out[mark["attrs"]["anchor"]] = (node.get("text", ""), mark["attrs"])
        for child in node.get("content") or []:
            walk(child)

    walk(content)
    return out


@router.put("/sections/{section_id}/content")
def edit(section_id: uuid.UUID, body: ContentIn, db: DB, user: Writer,
         validation: Revalidation) -> dict[str, Any]:  # fmt: skip
    section = _writable(db, section_id)
    before = _current(section)
    if (
        section.locked
        and not section.unlocked
        and _locked_nodes(body.content) != _locked_nodes(before.content)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, PROTECTED)
    old = _value_marks(before.content)
    new = _value_marks(body.content)
    refs = {r.anchor: r for r in before.value_refs}
    changed = [a for a, (text, _) in new.items() if a in old and old[a][0] != text]
    if changed and not body.confirm_values:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            {"message": "Confirme a alteração de valores que vêm da ficha-base.",
                             "anchors": changed})  # fmt: skip
    number = (db.scalar(select(func.max(SectionVersion.number)).where(
        SectionVersion.section_id == section.id)) or 0) + 1  # fmt: skip
    value_refs = []
    for anchor, (text, _) in new.items():
        ref = refs.get(anchor)
        if ref is None:
            continue
        edited = copy.deepcopy(ref.edited)
        if anchor in changed:
            edited = {
                "by": user.id,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "coe_01": True,
                "from_key": ref.key,
            }  # never the values (they may be personal)
        value_refs.append(ValueRef(
            anchor=anchor, key=ref.key, ficha_value_id=ref.ficha_value_id,
            circuit_id=ref.circuit_id, bom_item_id=ref.bom_item_id, field=ref.field,
            personal=ref.personal, rendered_text=None if ref.personal else text, edited=edited,
        ))  # fmt: skip
    for v in section.versions:
        if v.status == "current":
            v.status = "superseded"
    version = SectionVersion(section_id=section.id, number=number, content=body.content,
                             author_type="user", status="current", value_refs=value_refs,
                             missing_data=before.missing_data, assumptions=before.assumptions,
                             issues=before.issues)  # fmt: skip
    db.add(version)
    section.current_version = number
    if section.status == "reviewed":
        section.status = "generated"  # edited after the review: to review again
    _audit(db, user, "section.edited", section, version=number, values_changed=len(changed),
           note=body.note)  # fmt: skip
    db.commit()
    revalidate(db, validation, section.document.project_id, user.id)
    return {"version": number, "values_changed": len(changed)}
