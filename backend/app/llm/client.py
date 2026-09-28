"""Every request to the LLM goes through here (SPEC 6.1), whatever the provider.

In order: D5 (the project must allow the LLM), the privacy guard, the pace of the free quota,
retries with exponential backoff on 429/503, validation of the JSON with Pydantic (one retry with
the error in the request, then the caller leaves the section "todo"), and one LlmCall record
without the content of the request or of the answer.

When the main provider stays unavailable (5xx after the retries, e.g. Gemini's 503 "high
demand"), the same request (already checked by the guard) goes to the fallback provider, with
its own pace; the LlmCall records the provider and model that answered. A 429 (quota) does not
switch: the generation pauses as before.
"""

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.guard import PrivacyBlocked, PrivacyGuard, terms_for
from app.llm.provider import LlmProvider, Message, ProviderError
from app.llm.ratelimit import QuotaExhausted, RateLimiter
from app.models import LlmCall, Project
from app.profiles import personal_terms

T = TypeVar("T", bound=BaseModel)
Purpose = Literal["drafting", "extraction"]


class LlmNotAllowed(Exception):
    """D5: the terms of the Gemini API are pending; only projects from data/fixtures."""


class LlmFailed(Exception):
    """The request did not give a valid answer (the message is ours, for people)."""


class LlmPaused(LlmFailed):
    """The daily quota is used up: generation stops and resumes from the last block done."""


@dataclass
class LlmClient:
    provider: LlmProvider
    limiter: RateLimiter
    settings: Settings
    sleep: Callable[[float], None] = time.sleep
    on_wait: Callable[[float], None] | None = None  # "em fila" for the interface
    calls: list[LlmCall] = field(default_factory=list)
    fallback: LlmProvider | None = None
    fallback_limiter: RateLimiter | None = None

    def model_for(self, purpose: Purpose) -> str:
        name = self.settings.llm_model_drafting if purpose == "drafting" else (
            self.settings.llm_model_extraction
        )  # fmt: skip
        if not name:
            raise LlmFailed(f"Sem modelo definido para «{purpose}» (LLM_MODEL_* no .env).")
        return name

    def fallback_model_for(self, purpose: str) -> str:
        s = self.settings
        return (s.llm_fallback_model_drafting if purpose == "drafting"
                else s.llm_fallback_model_extraction) or s.llm_fallback_model_drafting  # fmt: skip

    def generate(
        self, db: Session, *, project: Project, purpose: Purpose, prompt_version: str,
        system: str, messages: list[Message], schema: type[T],
        section_id: uuid.UUID | None = None, profile: dict[str, str] | None = None,
        temperature: float = 0.2,
    ) -> tuple[T, LlmCall]:  # fmt: skip
        call = LlmCall(
            project_id=project.id, section_id=section_id, provider=self.provider.name,
            model=self.model_for(purpose), purpose=purpose, prompt_version=prompt_version,
            status="failed", attempts=0,
        )  # fmt: skip
        db.add(call)
        self.calls.append(call)
        started = time.monotonic()
        try:
            if not project.llm_allowed:
                call.status, call.error = (
                    "refused",
                    "D5 pendente: este projeto não pode usar o LLM.",
                )
                raise LlmNotAllowed(call.error)
            terms = terms_for(db, project.id, profile) + personal_terms(db, self.settings)
            guard = PrivacyGuard(terms)
            parts = {
                "system": system,
                **{f"mensagem {i}": m.text for i, m in enumerate(messages, 1)},
            }
            try:
                guard.enforce(parts)
            except PrivacyBlocked as exc:
                call.status, call.error = "blocked", str(exc)
                call.blocked = [f.as_json() for f in exc.findings]
                raise
            result = self._validated(call, system, list(messages), schema, temperature)
            call.status = "ok"
            return result, call
        finally:
            call.duration_ms = int((time.monotonic() - started) * 1000)
            db.flush()

    def _validated(self, call: LlmCall, system: str, messages: list[Message], schema: type[T],
                   temperature: float) -> T:  # fmt: skip
        json_schema = schema.model_json_schema()
        for attempt in (1, 2):
            raw = self._send(call, system, messages, json_schema, temperature)
            try:
                return schema.model_validate_json(raw)
            except ValidationError as exc:
                errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:10]]
                if attempt == 2:
                    call.status = "invalid"
                    call.error = f"Resposta do LLM inválida ({len(exc.errors())} erros de esquema)."
                    raise LlmFailed(call.error) from None
                messages = [
                    *messages,
                    Message("model", raw),
                    Message("user", "A resposta não cumpre o esquema JSON pedido. Erros: "
                            + json.dumps(errors, ensure_ascii=False)
                            + ". Devolve só o JSON corrigido, com o mesmo esquema."),
                ]  # fmt: skip
        raise AssertionError("unreachable")

    def _send(self, call: LlmCall, system: str, messages: list[Message],
              json_schema: dict[str, object], temperature: float) -> str:  # fmt: skip
        on_fallback = self.fallback is not None and call.provider == self.fallback.name
        if not on_fallback:
            try:
                return self._try(self.provider, self.limiter, call, system, messages,
                                 json_schema, temperature)  # fmt: skip
            except ProviderError as exc:
                if not (exc.unavailable and self.fallback and self.fallback_limiter):
                    call.error = str(exc)
                    raise LlmFailed(f"O LLM não respondeu: {exc}") from None
                main = str(exc)
            call.provider, call.model = self.fallback.name, self.fallback_model_for(call.purpose)
            if not call.model:
                call.error = f"{main} Sem modelo alternativo (LLM_FALLBACK_MODEL_*)."
                raise LlmFailed(f"O LLM não respondeu: {main}")
        assert self.fallback is not None and self.fallback_limiter is not None
        try:
            return self._try(self.fallback, self.fallback_limiter, call, system, messages,
                             json_schema, temperature)  # fmt: skip
        except ProviderError as exc:
            call.error = str(exc)
            raise LlmFailed(f"O LLM não respondeu (também o alternativo): {exc}") from None

    def _try(
        self,
        provider: LlmProvider,
        limiter: RateLimiter,
        call: LlmCall,
        system: str,
        messages: list[Message],
        json_schema: dict[str, object],
        temperature: float,
    ) -> str:
        """One provider, with its pace and retries. Raises the last ProviderError."""
        delay = self.settings.llm_backoff_s
        for retry in range(self.settings.llm_max_retries + 1):
            try:
                limiter.acquire(self.on_wait)
            except QuotaExhausted as exc:
                call.status, call.error = "failed", str(exc)
                raise LlmPaused(str(exc)) from None
            call.attempts += 1
            try:
                raw = provider.generate(
                    model=call.model, system=system, messages=messages,
                    json_schema=json_schema, temperature=temperature,
                )  # fmt: skip
            except ProviderError as exc:
                if not exc.retryable or retry == self.settings.llm_max_retries:
                    raise
                wait = max(delay, exc.retry_after_s or 0)
                if self.on_wait:
                    self.on_wait(wait)
                self.sleep(wait)
                delay *= 2
                continue
            call.input_tokens = (call.input_tokens or 0) + (raw.input_tokens or 0)
            call.output_tokens = (call.output_tokens or 0) + (raw.output_tokens or 0)
            return raw.text
        raise AssertionError("unreachable")


def make_provider(settings: Settings, name: str | None = None) -> LlmProvider:
    """The main provider, or the one called `name` (e.g. the fallback)."""
    name = name or settings.llm_provider
    if name == "fake":
        from app.llm.fake import FakeProvider

        return FakeProvider()
    if name == "groq":
        from app.llm.groq import GroqProvider

        return GroqProvider(settings.groq_api_key, settings.llm_timeout_s)
    from app.llm.gemini import GeminiProvider

    return GeminiProvider(settings.gemini_api_key, settings.llm_timeout_s)
