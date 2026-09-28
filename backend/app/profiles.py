"""Technicians' profiles: stored encrypted, read only in the backend (SPEC 8.5, P9).

Keys: tec.nome, tec.titulo, tec.nif, tec.cc, tec.oet, tec.dgeg, tec.email, tec.telefone,
tec.morada, tec.cp, tec.codigo_verificacao and doc.local (where the technician signs).
With DEV_AUTH, the development technician has an obviously fake profile when none was saved.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import TechnicianProfile

FIELDS = (
    "tec.nome", "tec.titulo", "tec.nif", "tec.cc", "tec.oet", "tec.dgeg", "tec.email",
    "tec.telefone", "tec.morada", "tec.cp", "tec.codigo_verificacao", "doc.local",
)  # fmt: skip
DEV_TECHNICIAN = "dev:tecnico"
DEV_PROFILE = {
    "tec.nome": "Técnico de Desenvolvimento",
    "tec.titulo": "engenheiro eletrotécnico (perfil de desenvolvimento)",
    "tec.nif": "000000000",
    "tec.cc": "00000000",
    "tec.oet": "00000",
    "tec.dgeg": "00000",
    "tec.email": "tecnico@desenvolvimento.invalid",
    "tec.telefone": "000 000 000",
    "tec.morada": "Morada de desenvolvimento",
    "tec.cp": "0000-000",
    "tec.codigo_verificacao": "dev00000",
    "doc.local": "Localidade (desenvolvimento)",
}


class ProfileUnavailable(Exception):
    """No key to encrypt profiles (PROFILE_ENCRYPTION_KEY)."""


def _fernet(settings: Settings) -> Fernet:
    if not settings.profile_encryption_key:
        raise ProfileUnavailable("PROFILE_ENCRYPTION_KEY não está definida (make env).")
    return Fernet(settings.profile_encryption_key.encode())


def save_profile(db: Session, settings: Settings, user_id: str, values: dict[str, Any]) -> None:
    data = {k: str(v).strip() for k, v in values.items() if k in FIELDS and str(v or "").strip()}
    token = _fernet(settings).encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()
    row = db.scalars(select(TechnicianProfile).where(TechnicianProfile.user_id == user_id)).first()
    if row is None:
        db.add(TechnicianProfile(user_id=user_id, data=token))
    else:
        row.data = token
    db.flush()


def profile_for(db: Session, settings: Settings, user_id: str | None) -> dict[str, str]:
    """The profile of a technician, or {} (the sections then say "falta dado")."""
    if not user_id:
        return {}
    row = db.scalars(select(TechnicianProfile).where(TechnicianProfile.user_id == user_id)).first()
    if row is not None and settings.profile_encryption_key:
        try:
            data: dict[str, str] = json.loads(_fernet(settings).decrypt(row.data.encode()))
            return data
        except InvalidToken:
            return {}
    if settings.dev_auth and user_id == DEV_TECHNICIAN:
        return dict(DEV_PROFILE)
    return {}


def personal_terms(db: Session, settings: Settings) -> list[tuple[str, str]]:
    """The personal fields of every saved profile, for the privacy guard (never logged)."""
    from app.assembly.values import PERSONAL_DOC_KEYS

    if not settings.profile_encryption_key:
        return []
    terms = []
    for row in db.scalars(select(TechnicianProfile)):
        try:
            data = json.loads(_fernet(settings).decrypt(row.data.encode()))
        except InvalidToken:
            continue
        terms += [("profile", v) for k, v in data.items() if v and k in PERSONAL_DOC_KEYS]
    return terms


def revision_profile(db: Session, settings: Settings, revision: Any) -> dict[str, str]:
    """The profile of the technician who confirmed the ficha-base: the one who signs."""
    return profile_for(db, settings, getattr(revision, "confirmed_by", None))
