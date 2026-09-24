from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import DEV_USERS, ROLE_LABELS_PT, ROLES, CurrentUser, User
from app.config import Settings, get_settings

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
