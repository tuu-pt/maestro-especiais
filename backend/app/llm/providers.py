"""The three LLM providers, the main one and the order of the others (8 Oct 2026).

The main provider is chosen by the admin (screen Definições, stored in `app_setting`); without a
choice it is LLM_PROVIDER. A request goes to the main one and, when it fails (unavailable, no
connection, quota used up, after the retries), to the next one: the others in the order
gemini, groq, claude. A provider without its API key or without a model is left out. No key is
ever shown: only whether it is set.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppSetting

PROVIDERS = ("gemini", "groq", "claude")
LABELS = {"gemini": "Gemini (Google)", "groq": "Groq", "claude": "Claude (Anthropic)",
          "fake": "Simulado (testes)"}  # fmt: skip
PRIMARY_KEY = "llm.primary"
DEFAULT_PACE = {"gemini": (10, 200), "groq": (2, 200), "claude": (20, 1000), "fake": (100, 1000)}
PURPOSES = ("drafting", "extraction")


@dataclass
class ProviderConfig:
    name: str
    label: str
    key_set: bool
    models: dict[str, str]  # purpose -> model ("" when not set)
    rpm: int
    rpd: int

    @property
    def configured(self) -> bool:
        return self.key_set and bool(self.models.get("drafting") or self.models.get("extraction"))

    def as_json(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, "key_set": self.key_set,
                "models": self.models, "rpm": self.rpm, "rpd": self.rpd,
                "configured": self.configured}  # fmt: skip


def _key_set(settings: Settings, name: str) -> bool:
    keys = {"gemini": settings.gemini_api_key, "groq": settings.groq_api_key,
            "claude": settings.anthropic_api_key}  # fmt: skip
    return name == "fake" or bool(keys.get(name))


def config(settings: Settings, name: str) -> ProviderConfig:
    """A provider's models and pace: its own variables, else the old ones (LLM_MODEL_* for
    LLM_PROVIDER, LLM_FALLBACK_* for LLM_FALLBACK_PROVIDER)."""
    own = {p: getattr(settings, f"llm_{name}_model_{p}", "") or "" for p in PURPOSES}
    if settings.llm_provider == name:
        old = {"drafting": settings.llm_model_drafting,
               "extraction": settings.llm_model_extraction}  # fmt: skip
        pace = (settings.llm_rpm, settings.llm_rpd)
    elif settings.llm_fallback_provider == name:
        old = {"drafting": settings.llm_fallback_model_drafting,
               "extraction": settings.llm_fallback_model_extraction
               or settings.llm_fallback_model_drafting}  # fmt: skip
        pace = (settings.llm_fallback_rpm, settings.llm_fallback_rpd)
    else:
        old, pace = {}, DEFAULT_PACE.get(name, (10, 200))
    models = {p: own[p] or old.get(p, "") or "" for p in PURPOSES}
    rpm = getattr(settings, f"llm_{name}_rpm", None) or pace[0]
    rpd = getattr(settings, f"llm_{name}_rpd", None) or pace[1]
    return ProviderConfig(name, LABELS.get(name, name), _key_set(settings, name), models,
                          rpm, rpd)  # fmt: skip


def primary(db: Session | None, settings: Settings) -> str:
    row = (db.scalars(select(AppSetting).where(AppSetting.key == PRIMARY_KEY)).first()
           if db is not None else None)  # fmt: skip
    if row is not None and isinstance(row.value, str):
        return row.value
    return settings.llm_provider


def order(main: str) -> list[str]:
    """The main provider first, then the others in the fixed order."""
    names = [main] if main else []
    return names + [p for p in PROVIDERS if p != main]


def chain(db: Session | None, settings: Settings) -> list[ProviderConfig]:
    """The providers a request may use, in order: only the configured ones."""
    return [c for c in (config(settings, n) for n in order(primary(db, settings))) if c.configured]
