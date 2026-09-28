from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.values import PERSONAL_DOC_KEYS
from app.audit import record
from app.auth import DEV_USERS, ROLE_LABELS_PT, ROLES, CurrentUser, User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.library.facts import DOC_KEYS
from app.models import TechnicianProfile
from app.profiles import FIELDS, ProfileUnavailable, profile_for, save_profile

router = APIRouter(tags=["utilizador"])


class RoleOut(BaseModel):
    id: str
    label: str


class UserOut(BaseModel):
    id: str
    name: str
    roles: list[RoleOut]

    @classmethod
    def of(cls, user: User) -> "UserOut":
        roles = [RoleOut(id=r, label=ROLE_LABELS_PT[r]) for r in ROLES if r in user.roles]
        return cls(id=user.id, name=user.name, roles=roles)


class DevUserOut(UserOut):
    login: str


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)


@router.get("/dev/users")
def dev_users(settings: Annotated[Settings, Depends(get_settings)]) -> list[DevUserOut]:
    """Users the development switcher can pick. Absent outside development."""
    if not settings.dev_auth:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return [DevUserOut(login=login, **UserOut.of(u).model_dump()) for login, u in DEV_USERS.items()]


# ---------------------------------------------------------------- technician's profile (SPEC 8.5)


class ProfileField(BaseModel):
    key: str
    label: str
    personal: bool
    filled: bool
    value: str | None  # only the fields that are not personal; the others stay "•••"


class ProfileOut(BaseModel):
    source: str  # saved | development | none
    fields: list[ProfileField]


class ProfileIn(BaseModel):
    values: dict[str, str]  # "" clears a field


Technician = Annotated[User, Depends(require_role("tecnico"))]
DB = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


def _profile_out(db: Session, settings: Settings, user: User) -> ProfileOut:
    data = profile_for(db, settings, user.id)
    saved = db.scalars(
        select(TechnicianProfile).where(TechnicianProfile.user_id == user.id)
    ).first()
    source = "saved" if saved else ("development" if data else "none")
    fields = [
        ProfileField(
            key=k,
            label=DOC_KEYS.get(k, k),
            personal=k in PERSONAL_DOC_KEYS,
            filled=bool(data.get(k)),
            value=None if k in PERSONAL_DOC_KEYS else data.get(k),
        )
        for k in FIELDS
    ]
    return ProfileOut(source=source, fields=fields)


@router.get("/me/profile")
def read_profile(db: DB, settings: Config, user: Technician) -> ProfileOut:
    return _profile_out(db, settings, user)


@router.put("/me/profile")
def update_profile(body: ProfileIn, db: DB, settings: Config, user: Technician) -> ProfileOut:
    unknown = sorted(set(body.values) - set(FIELDS))
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Campos desconhecidos: {unknown}"
        )
    merged = {**profile_for(db, settings, user.id), **body.values}
    try:
        save_profile(db, settings, user.id, merged)
    except ProfileUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    record(db, user, "profile.updated", "technician_profile", None,
           {"fields": sorted(body.values)}, project_id=None)  # fmt: skip
    db.commit()
    return _profile_out(db, settings, user)
