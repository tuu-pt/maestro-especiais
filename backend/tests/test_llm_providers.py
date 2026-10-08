"""The three providers, the main one chosen by the admin, the order of the others (8 Oct)."""

from typing import Any

import pytest
from conftest import Api
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.llm.providers import chain, config, order, primary
from app.models import AuditEvent

# the .env of 28 Sep 2026: Gemini first, Groq as the fallback, with the old variables
OLD_ENV = Settings(
    llm_provider="gemini", gemini_api_key="g", groq_api_key="q",
    llm_model_drafting="gemini-modelo", llm_model_extraction="gemini-modelo",
    llm_fallback_provider="groq", llm_fallback_model_drafting="groq-modelo",
    llm_fallback_rpm=2, llm_rpm=10,
)  # fmt: skip


def test_the_old_variables_still_configure_gemini_and_groq() -> None:
    gemini, groq, claude = (config(OLD_ENV, n) for n in ("gemini", "groq", "claude"))

    assert gemini.models == {"drafting": "gemini-modelo", "extraction": "gemini-modelo"}
    assert groq.models == {"drafting": "groq-modelo", "extraction": "groq-modelo"}
    assert (gemini.rpm, groq.rpm) == (10, 2)
    assert gemini.configured and groq.configured and not claude.configured  # no key, no model


def test_the_own_variables_win_and_claude_comes_in_with_a_key_and_a_model() -> None:
    settings = OLD_ENV.model_copy(update={
        "anthropic_api_key": "a", "llm_claude_model_drafting": "claude-modelo",
        "llm_groq_model_drafting": "outro-groq", "llm_claude_rpm": 7})  # fmt: skip

    assert config(settings, "groq").models["drafting"] == "outro-groq"
    claude = config(settings, "claude")
    assert claude.configured and claude.rpm == 7
    assert [c.name for c in chain(None, settings)] == ["gemini", "groq", "claude"]


def test_the_main_one_first_then_the_others_in_order() -> None:
    assert order("claude") == ["claude", "gemini", "groq"]
    assert order("groq") == ["groq", "gemini", "claude"]


# ---------------------------------------------------------------- screen Definições


@pytest.fixture
def configured(app: FastAPI) -> Settings:
    settings = OLD_ENV.model_copy(update={"dev_auth": True})
    app.dependency_overrides[get_settings] = lambda: settings
    return settings


def test_everyone_sees_the_providers_but_never_a_key(api: Api, configured: Settings) -> None:
    body: dict[str, Any] = api.as_("redator").get("/api/settings/llm").json()

    assert body["primary"] == "gemini" and body["order"] == ["gemini", "groq"]
    claude = next(p for p in body["providers"] if p["name"] == "claude")
    assert claude == {**claude, "configured": False, "key_set": False}
    assert "g" not in [v for p in body["providers"] for v in p.values() if isinstance(v, str)]


def test_only_the_admin_chooses_the_main_one_and_it_is_audited(
    api: Api, db: Session, configured: Settings
) -> None:
    body = {"primary": "groq", "reason": "O Gemini anda em 503."}
    assert api.as_("tecnico").put("/api/settings/llm", json=body).status_code == 403
    refused = api.as_("admin").put("/api/settings/llm",
                                   json={"primary": "claude", "reason": "Teste."})  # fmt: skip
    assert refused.status_code == 422 and "falta a chave" in refused.json()["detail"]

    changed = api.as_("admin").put("/api/settings/llm", json=body)

    assert changed.status_code == 200 and changed.json()["order"] == ["groq", "gemini"]
    assert primary(db, configured) == "groq"
    assert [c.name for c in chain(db, configured)] == ["groq", "gemini"]
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "settings.llm_primary")).one()
    assert event.payload == {"from": "gemini", "to": "groq", "reason": "O Gemini anda em 503."}
