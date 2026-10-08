"""Sign in and out with an email and a password (app/accounts.py, until D6)."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.accounts import (
    COOKIE,
    SessionUnavailable,
    account_from_token,
    as_user,
    authenticate,
    session_token,
)
from app.api.me import UserOut
from app.audit import record
from app.config import Settings, get_settings
from app.db import get_session

router = APIRouter(prefix="/auth", tags=["sessão"])
DB = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]
INVALID = "Email ou password inválidos. Tente novamente."


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn, response: Response, db: DB, settings: Config) -> UserOut:
    if not settings.session_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "O início de sessão não está configurado (SESSION_SECRET).",
        )
    account = authenticate(db, body.email, body.password)
    if account is None:
        db.commit()  # the failed attempt counts
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID)
    try:
        token = session_token(settings, account)
    except SessionUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    user = as_user(account)
    record(db, user, "auth.login", "app_user", account.id, {}, project_id=None)
    db.commit()
    response.set_cookie(
        COOKIE, token, max_age=settings.session_ttl_hours * 3600, httponly=True,
        samesite="lax", secure=settings.session_cookie_secure, path="/",
    )  # fmt: skip
    return UserOut.of(user)


@router.post("/logout")
def logout(
    response: Response,
    db: DB,
    settings: Config,
    maestro_session: Annotated[str | None, Cookie()] = None,
) -> dict[str, bool]:
    account = account_from_token(db, settings, maestro_session) if maestro_session else None
    if account is not None:
        record(db, as_user(account), "auth.logout", "app_user", account.id, {}, project_id=None)
        db.commit()
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax",
                           secure=settings.session_cookie_secure)  # fmt: skip
    return {"ended": True}
