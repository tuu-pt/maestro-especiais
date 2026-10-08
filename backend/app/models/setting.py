"""Settings of the application changed by the admin at runtime (e.g. the main LLM provider).

Only what the screen Definições sets; secrets and model names stay in the environment. Every
change is audited.
"""

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Entity


class AppSetting(Entity):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(64))
