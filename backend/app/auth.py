"""Who is calling, and may they? (SPEC 4, 12.1: roles checked on every endpoint).

Accounts sign in with an email and a password and carry a session cookie (app/accounts.py,
until D6). In development (DEV_AUTH) the simulated users picked with the X-Dev-User header also
work; the cookie wins. An SSO (D6) will replace current_user only; require_role stays the same.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session

ROLES = ("redator", "tecnico", "curador", "admin")
ROLE_LABELS_PT = {
    "redator": "Redator",
    "tecnico": "Técnico responsável",
    "curador": "Curador",
    "admin": "Administrador",
}


@dataclass(frozen=True)
class User:
    id: str
    name: str
    roles: frozenset[str]
    via: str = "dev"  # dev (X-Dev-User) | account (session cookie)

    def has_any(self, roles: tuple[str, ...]) -> bool:
        return bool(self.roles & set(roles))


# Generic names on purpose: no fictitious people. The técnico can do everything the
# redator can (SPEC 4).
DEV_USERS: dict[str, User] = {
    "redator": User("dev:redator", "Redator (desenvolvimento)", frozenset({"redator"})),
    "tecnico": User(
        "dev:tecnico", "Técnico responsável (desenvolvimento)", frozenset({"redator", "tecnico"})
    ),
    "curador": User("dev:curador", "Curador (desenvolvimento)", frozenset({"curador"})),
    "admin": User("dev:admin", "Administrador (desenvolvimento)", frozenset({"admin"})),
}


def current_user(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_session)],
    x_dev_user: Annotated[str | None, Header()] = None,
    maestro_session: Annotated[str | None, Cookie()] = None,
) -> User:
    if maestro_session:
        from app.accounts import account_from_token, as_user

        account = account_from_token(db, settings, maestro_session)
        if account is not None:
            return as_user(account)
    if not settings.dev_auth:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão não iniciada.")
    user = DEV_USERS.get(x_dev_user or "")
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilizador de desenvolvimento inválido.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: str) -> Callable[[User], User]:
    """Dependency that lets the call through only for users with one of the roles."""
    unknown = set(roles) - set(ROLES)
    if unknown:
        raise ValueError(f"unknown roles: {sorted(unknown)}")

    def check(user: CurrentUser) -> User:
        if not user.has_any(roles):
            names = ", ".join(ROLE_LABELS_PT[r] for r in roles)
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Esta ação exige o papel: {names}.")
        return user

    return check
