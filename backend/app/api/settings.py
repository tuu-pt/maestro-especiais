"""Settings of the application (screen Definições): the LLM providers and the main one.

Everyone sees which providers are ready (key and model set; never the key itself) and the order a
request follows; only the admin chooses the main one, with a reason, and the choice is audited.
The worker reads it at each job: no restart.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.llm.providers import PRIMARY_KEY, PROVIDERS, config, order, primary
from app.models import AppSetting

router = APIRouter(prefix="/settings", tags=["definições"])

DB = Annotated[Session, Depends(get_session)]
Admin = Annotated[User, Depends(require_role("admin"))]
Config = Annotated[Settings, Depends(get_settings)]


class ProviderOut(BaseModel):
    name: str
    label: str
    key_set: bool
    models: dict[str, str]
    rpm: int
    rpd: int
    configured: bool


class LlmSettingsOut(BaseModel):
    primary: str
    order: list[str]  # what a request follows now: only the configured providers
    providers: list[ProviderOut]


class PrimaryIn(BaseModel):
    primary: Literal["gemini", "groq", "claude"]
    reason: str = Field(min_length=3, max_length=500)


def _out(db: Session, settings: Settings) -> LlmSettingsOut:
    main = primary(db, settings)
    configs = [config(settings, name) for name in PROVIDERS]
    ready = {c.name for c in configs if c.configured}
    return LlmSettingsOut(
        primary=main, order=[n for n in order(main) if n in ready],
        providers=[ProviderOut(**c.as_json()) for c in configs],
    )  # fmt: skip


@router.get("/llm")
def llm_settings(db: DB, settings: Config, _: CurrentUser) -> LlmSettingsOut:
    return _out(db, settings)


@router.put("/llm")
def set_primary(body: PrimaryIn, db: DB, settings: Config, user: Admin) -> LlmSettingsOut:
    chosen = config(settings, body.primary)
    if not chosen.configured:
        missing = "a chave" if not chosen.key_set else "o modelo"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"{chosen.label}: falta {missing} no .env.")  # fmt: skip
    before = primary(db, settings)
    row = db.scalars(select(AppSetting).where(AppSetting.key == PRIMARY_KEY)).first()
    if row is None:
        row = AppSetting(id=uuid.uuid4(), key=PRIMARY_KEY, created_by=user.id)
        db.add(row)
    row.value, row.updated_by, row.updated_at = body.primary, user.id, datetime.now(UTC)
    payload: dict[str, Any] = {"from": before, "to": body.primary, "reason": body.reason.strip()}
    record(db, user, "settings.llm_primary", "app_setting", row.id, payload, project_id=None)
    db.commit()
    return _out(db, settings)
