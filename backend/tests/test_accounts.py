"""Accounts with an email and a password, and the session cookie (until D6, 8 Oct 2026)."""

import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import Api
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts
from app.accounts import (
    COOKIE,
    account_from_token,
    check_password,
    create_or_update,
    hash_password,
    name_of,
    names,
    session_token,
    technicians,
)
from app.config import Settings, get_settings
from app.models import AppUser, AuditEvent

PASSWORD = secrets.token_urlsafe(12)  # a test value, made here


def with_settings(app: FastAPI, **values: Any) -> Settings:
    settings = Settings(session_secret=secrets.token_urlsafe(16), session_cookie_secure=False,
                        **values)  # fmt: skip
    app.dependency_overrides[get_settings] = lambda: settings
    return settings


@pytest.fixture
def account(db: Session) -> AppUser:
    return create_or_update(db, " Tecnica@Exemplo.test ", "Técnica de Teste", ["tecnico"], PASSWORD)


@pytest.fixture
def signed(app: FastAPI) -> Settings:
    return with_settings(app, dev_auth=False)


def login(api: Api, email: str = "tecnica@exemplo.test", password: str = PASSWORD) -> Any:
    return api.as_(None).post("/api/auth/login", json={"email": email, "password": password})


def test_passwords_are_hashed_and_checked() -> None:
    stored = hash_password(PASSWORD)
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert check_password(PASSWORD, stored)
    assert not check_password(PASSWORD + "x", stored)
    assert not check_password(PASSWORD, "lixo")


def test_an_account_has_a_lower_case_email_and_the_tecnico_is_also_redator(
    db: Session, account: AppUser
) -> None:
    assert account.email == "tecnica@exemplo.test"
    assert account.roles == ["redator", "tecnico"]
    with pytest.raises(ValueError, match="Papéis desconhecidos"):
        create_or_update(db, account.email, "X", ["chefe"], None)
    with pytest.raises(ValueError, match="pelo menos 10"):
        create_or_update(db, "outra@exemplo.test", "Outra", ["redator"], "curta")


def test_signing_in_sets_the_cookie_and_me_is_the_account(
    api: Api, db: Session, account: AppUser, signed: Settings
) -> None:
    response = login(api)

    assert response.status_code == 200
    assert response.json()["session"] == "account"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=") and "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    me = api.client.get("/api/me").json()
    assert me["id"] == account.user_id and me["name"] == "Técnica de Teste"
    assert [r["id"] for r in me["roles"]] == ["redator", "tecnico"]
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.login")).one()
    assert event.actor_id == account.user_id and event.payload == {}  # never the email


@pytest.mark.parametrize("email, password", [("tecnica@exemplo.test", "errada-1234"),
                                             ("ninguem@exemplo.test", PASSWORD)])  # fmt: skip
def test_one_same_answer_for_a_wrong_password_or_an_unknown_email(
    api: Api, account: AppUser, signed: Settings, email: str, password: str
) -> None:
    response = login(api, email, password)

    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou password inválidos. Tente novamente."
    assert COOKIE not in response.headers.get("set-cookie", "")


def test_five_wrong_passwords_lock_the_account_for_a_while(
    api: Api, db: Session, account: AppUser, signed: Settings
) -> None:
    for _ in range(accounts.MAX_FAILURES):
        assert login(api, password="errada-1234").status_code == 401

    assert login(api).status_code == 401  # even the right one, while locked
    account.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert login(api).status_code == 200


def test_without_dev_auth_the_development_header_is_ignored(api: Api, signed: Settings) -> None:
    response = api.as_("admin").get("/api/me")

    assert response.status_code == 401 and response.json()["detail"] == "Sessão não iniciada."


def test_in_development_the_signed_in_account_wins_over_the_header(
    api: Api, app: FastAPI, account: AppUser
) -> None:
    with_settings(app, dev_auth=True)
    assert login(api).status_code == 200

    me = api.as_("admin").get("/api/me").json()

    assert me["id"] == account.user_id and me["session"] == "account"


def test_signing_out_ends_the_session(
    api: Api, db: Session, account: AppUser, signed: Settings
) -> None:
    login(api)

    assert api.client.post("/api/auth/logout").status_code == 200
    assert api.client.get("/api/me").status_code == 401
    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.logout")).one()


def test_a_session_ends_when_the_account_is_off_or_its_password_changes(
    db: Session, account: AppUser
) -> None:
    settings = Settings(session_secret=secrets.token_urlsafe(16))
    token = session_token(settings, account)
    assert account_from_token(db, settings, token) is account

    create_or_update(db, account.email, account.name, ["tecnico"], secrets.token_urlsafe(12))
    assert account_from_token(db, settings, token) is None
    token = session_token(settings, account)
    account.active = False
    assert account_from_token(db, settings, token) is None


def test_a_tampered_an_expired_or_a_foreign_token_is_refused(db: Session, account: AppUser) -> None:
    settings = Settings(session_secret=secrets.token_urlsafe(16), session_ttl_hours=1)
    token = session_token(settings, account)
    account_id, expires, stamp, signature = token.split(".")

    later = str(int(expires) + 3600)
    assert account_from_token(db, settings, f"{account_id}.{later}.{stamp}.{signature}") is None
    assert account_from_token(db, settings, token, now=time.time() + 2 * 3600) is None
    other = Settings(session_secret=secrets.token_urlsafe(16))
    assert account_from_token(db, other, token) is None
    assert account_from_token(db, settings, "lixo") is None


def test_without_a_session_secret_nobody_signs_in(api: Api, app: FastAPI, account: AppUser) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(dev_auth=False)

    response = login(api)

    assert response.status_code == 503 and "SESSION_SECRET" in response.json()["detail"]


def test_names_and_technicians_come_from_the_accounts(db: Session, account: AppUser) -> None:
    create_or_update(db, "curador@exemplo.test", "Curador de Teste", ["curador"], PASSWORD)

    assert name_of(db, account.user_id) == "Técnica de Teste"
    assert names(db)[account.user_id] == "Técnica de Teste"
    assert [u.id for u in technicians(db, with_dev=False)] == [account.user_id]
    assert "dev:tecnico" in [u.id for u in technicians(db, with_dev=True)]


def test_the_command_creates_an_account_asking_for_the_password(
    db: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Kept:  # the test session, which the command must not close
        def __getattr__(self, name: str) -> Callable[..., Any]:
            return (lambda *a, **k: None) if name == "close" else getattr(db, name)

    monkeypatch.setattr("app.db.get_session", lambda: iter([Kept()]))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSWORD)

    code = accounts.main(["create", "Novo@Exemplo.test", "Novo Redator", "--roles", "redator"])

    assert code == 0 and "OK: novo@exemplo.test (redator)" in capsys.readouterr().out
    created = accounts.find(db, "novo@exemplo.test")
    assert created is not None and check_password(PASSWORD, created.password_hash)
