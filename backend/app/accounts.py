"""Accounts with an email and a password, and the session cookie (until D6).

As in the TUU's Registo de Temas Estratégicos: the admin creates the accounts with
`make create-user` (no sign-up page) and people sign in on the login page. Differences, on purpose:
the password is hashed with scrypt (standard library, no new dependency); the session is an
HMAC-signed cookie with only the account id, so the roles and the active flag are read from the
database on every request; changing the password ends the other sessions; five wrong passwords
lock the account for 15 minutes.

Neither the email nor the password is ever logged; the audit keeps the account id.
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import secrets
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import DEV_USERS, ROLES, User
from app.config import Settings
from app.models import AppUser

COOKIE = "maestro_session"
MIN_PASSWORD = 10
MAX_FAILURES = 5
LOCK = timedelta(minutes=15)
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class SessionUnavailable(Exception):
    """No SESSION_SECRET: nobody can sign in (make env-update)."""


# ---------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    n, r, p = _SCRYPT["n"], _SCRYPT["r"], _SCRYPT["p"]
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(digest)}"


def check_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        mine = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(mine, _unb64(digest))


def password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD:
        return f"A password tem de ter pelo menos {MIN_PASSWORD} caracteres."
    return None


# ---------------------------------------------------------------- session cookie


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _secret(settings: Settings) -> bytes:
    if not settings.session_secret:
        raise SessionUnavailable("SESSION_SECRET não está definida (make env-update).")
    return settings.session_secret.encode()


def _stamp(account: AppUser) -> str:
    """Changes with the password: the sessions opened before it stop working."""
    return hashlib.sha256(account.password_hash.encode()).hexdigest()[:16]


def _sign(settings: Settings, payload: str) -> str:
    return _b64(hmac.new(_secret(settings), payload.encode(), hashlib.sha256).digest())


def session_token(settings: Settings, account: AppUser, now: float | None = None) -> str:
    expires = int((now or time.time()) + settings.session_ttl_hours * 3600)
    payload = f"{account.id}.{expires}.{_stamp(account)}"
    return f"{payload}.{_sign(settings, payload)}"


def account_from_token(
    db: Session, settings: Settings, token: str, now: float | None = None
) -> AppUser | None:
    try:
        account_id, expires, stamp, signature = token.split(".")
        payload = f"{account_id}.{expires}.{stamp}"
        if not hmac.compare_digest(signature, _sign(settings, payload)):
            return None
        if int(expires) < (now or time.time()):
            return None
        account = db.get(AppUser, uuid.UUID(account_id))
    except (ValueError, SessionUnavailable):
        return None
    if account is None or not account.active or stamp != _stamp(account):
        return None
    return account


def as_user(account: AppUser) -> User:
    return User(account.user_id, account.name, frozenset(account.roles), "account")


# ---------------------------------------------------------------- signing in


def _now() -> datetime:
    return datetime.now(UTC)


def find(db: Session, email: str) -> AppUser | None:
    return db.scalars(select(AppUser).where(AppUser.email == email.strip().lower())).first()


def authenticate(db: Session, email: str, password: str) -> AppUser | None:
    """The account, or None with one same answer for an unknown email, a wrong password, an
    inactive or a locked account (the page says only «Email ou password inválidos»)."""
    account = find(db, email)
    if account is None:
        check_password(password, hash_password("x" * MIN_PASSWORD))  # about the same time
        return None
    if account.locked_until and account.locked_until > _now():
        return None
    if not check_password(password, account.password_hash) or not account.active:
        account.failed_logins += 1
        if account.failed_logins >= MAX_FAILURES:
            account.locked_until = _now() + LOCK
            account.failed_logins = 0
        db.flush()
        return None
    account.failed_logins = 0
    account.locked_until = None
    account.last_login_at = _now()
    db.flush()
    return account


# ---------------------------------------------------------------- accounts


def normal_roles(roles: list[str]) -> list[str]:
    unknown = sorted(set(roles) - set(ROLES))
    if unknown:
        raise ValueError(f"Papéis desconhecidos: {unknown}. Possíveis: {', '.join(ROLES)}.")
    wanted = set(roles) | ({"redator"} if "tecnico" in roles else set())  # SPEC 4
    return [r for r in ROLES if r in wanted]


def create_or_update(
    db: Session, email: str, name: str, roles: list[str], password: str | None
) -> AppUser:
    """Creates the account, or updates its name, roles (and password, when given)."""
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Email inválido.")
    account = find(db, email)
    if password is not None and (problem := password_problem(password)):
        raise ValueError(problem)
    if account is None:
        if password is None:
            raise ValueError("Uma conta nova precisa de uma password.")
        account = AppUser(id=uuid.uuid4(), email=email, name=name.strip(), roles=[],
                          password_hash=hash_password(password))  # fmt: skip
        db.add(account)
    account.name = name.strip() or account.name
    account.roles = normal_roles(roles)
    account.active = True
    if password is not None:
        account.password_hash = hash_password(password)
        account.failed_logins, account.locked_until = 0, None
    db.flush()
    return account


def names(db: Session) -> dict[str, str]:
    """User id → name, for the audit and the documents (development users and accounts)."""
    found = {u.id: u.name for u in DEV_USERS.values()}
    found.update({a.user_id: a.name for a in db.scalars(select(AppUser))})
    return found


def name_of(db: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    if user_id.startswith("user:"):
        try:
            account = db.get(AppUser, uuid.UUID(user_id.removeprefix("user:")))
        except ValueError:
            account = None
        return account.name if account else user_id
    return next((u.name for u in DEV_USERS.values() if u.id == user_id), user_id)


def technicians(db: Session, with_dev: bool) -> list[User]:
    """Who may be the técnico responsável: the active accounts with the role (and, for a
    development user, the development técnico)."""
    found = [u for u in DEV_USERS.values() if "tecnico" in u.roles] if with_dev else []
    accounts = db.scalars(select(AppUser).where(AppUser.active).order_by(AppUser.name))
    return found + [as_user(a) for a in accounts if "tecnico" in a.roles]


# ---------------------------------------------------------------- make create-user


def _ask_password() -> str:
    first = getpass.getpass("Password (não aparece): ")
    if first != getpass.getpass("Repetir a password: "):
        raise ValueError("As passwords não coincidem.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.accounts", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="cria ou atualiza uma conta (pede a password)")
    create.add_argument("email")
    create.add_argument("name")
    create.add_argument("--roles", default="redator", help=f"separados por vírgulas: {ROLES}")
    create.add_argument("--keep-password", action="store_true", help="só muda o nome e os papéis")
    for command in ("password", "deactivate"):
        sub.add_parser(command).add_argument("email")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    from app.db import get_session

    db = next(get_session())
    try:
        if args.command == "list":
            for a in db.scalars(select(AppUser).order_by(AppUser.email)):
                state = "ativa" if a.active else "desativada"
                print(f"{a.email}\t{a.name}\t{','.join(a.roles)}\t{state}")
            return 0
        if args.command == "create":
            roles = [r.strip() for r in args.roles.split(",") if r.strip()]
            password = None if args.keep_password else _ask_password()
            account = create_or_update(db, args.email, args.name, roles, password)
        else:
            account = find(db, args.email)  # type: ignore[assignment]
            if account is None:
                raise ValueError("Não há conta com esse email.")
            if args.command == "password":
                if problem := password_problem(password := _ask_password()):
                    raise ValueError(problem)
                account.password_hash = hash_password(password)
                account.failed_logins, account.locked_until = 0, None
            else:
                account.active = False
        db.commit()
        print(f"OK: {account.email} ({', '.join(account.roles)}"
              f"{'' if account.active else ', desativada'})")  # fmt: skip
        return 0
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
