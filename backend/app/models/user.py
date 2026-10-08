"""Accounts that sign in with an email and a password (until D6 decides an SSO).

Created by the admin with `make create-user`, as in the TUU's Registo de Temas Estratégicos; no
sign-up page. The roles are read from here on every request, so a change takes effect at once.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity


class AppUser(Entity):
    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(String(254), unique=True)  # lower case
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(default=True, server_default="true")
    failed_logins: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def user_id(self) -> str:
        """The id the audit, the profiles and the documents keep (like "dev:tecnico")."""
        return f"user:{self.id}"
