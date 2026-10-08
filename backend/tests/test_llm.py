"""LLM layer (SPEC 6.1): D5, privacy guard, pace, retries, validation, LlmCall (Phase 4, task 3).

No test here uses the network: the provider is FakeProvider.
"""

import json
from typing import Any

import pytest
from conftest import Api
from pydantic import BaseModel
from reference_projects import FIXTURES, have_fixtures, load_confirmed
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.blocked import names_in, seed_blocked_terms
from app.llm.client import LlmClient, LlmFailed, LlmNotAllowed, make_provider
from app.llm.fake import FakeProvider
from app.llm.gemini import GeminiProvider
from app.llm.guard import PrivacyBlocked, PrivacyGuard, terms_for
from app.llm.provider import Message, ProviderError
from app.llm.ratelimit import MemoryRateLimiter, QuotaExhausted, RedisRateLimiter
from app.models import LlmCall, Project

pytestmark = pytest.mark.usefixtures("inline_ingestion")


class Answer(BaseModel):
    text: str


SETTINGS = Settings(llm_model_drafting="modelo-de-teste", llm_max_retries=2, llm_backoff_s=1.0)


def client(provider: FakeProvider, **kw: Any) -> tuple[LlmClient, list[float]]:
    waits: list[float] = []
    limiter = MemoryRateLimiter(rpm=100, rpd=100, sleep=lambda s: None)
    return LlmClient(provider, limiter, SETTINGS, sleep=waits.append, **kw), waits


def project(db: Session, allowed: bool = True) -> Project:
    p = Project(
        code=f"T{len(db.scalars(select(Project)).all())}", name="Teste", llm_allowed=allowed
    )
    db.add(p)
    db.flush()
    return p


def ask(c: LlmClient, db: Session, p: Project, text: str = "Olá") -> tuple[Answer, LlmCall]:
    messages = [Message("user", text)]
    return c.generate(db, project=p, purpose="drafting", prompt_version="teste_v1",
                      system="Sistema", messages=messages, schema=Answer)  # fmt: skip


# ---------------------------------------------------------------- D5


def test_a_project_without_llm_allowed_never_reaches_the_provider(db: Session) -> None:
    fake = FakeProvider(['{"text": "x"}'])
    c, _ = client(fake)

    with pytest.raises(LlmNotAllowed, match="LLM desligado"):
        ask(c, db, project(db, allowed=False))

    assert fake.sent == []
    [call] = db.scalars(select(LlmCall)).all()
    assert call.status == "refused" and call.attempts == 0


# ---------------------------------------------------------------- privacy guard


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Contacto: ana.exemplo@mail.pt", "email"),
        ("NIF 123456789 do requerente", "nif"),
        ("Cartão de cidadão CC 12345678", "cc"),
        ("Telefone 912 345 678", "phone"),
        ("Inscrito na DGEG com o n.º 12345", "dgeg_oet"),
        ("Membro OET: 00001", "dgeg_oet"),
    ],
)
def test_the_guard_blocks_personal_data_patterns(db: Session, text: str, kind: str) -> None:
    fake = FakeProvider(['{"text": "x"}'])
    c, _ = client(fake)

    with pytest.raises(PrivacyBlocked) as blocked:
        ask(c, db, project(db), f"Texto do bloco. {text}.")

    assert fake.sent == []  # nothing was sent
    assert kind in {f.kind for f in blocked.value.findings}
    call = db.scalars(select(LlmCall)).one()
    assert call.status == "blocked"
    assert {"kind": kind, "where": "mensagem 1"} in call.blocked
    assert text.split()[-1] not in (call.error or "") + json.dumps(call.blocked)  # never the value


def test_placeholders_pass_the_guard() -> None:
    guard = PrivacyGuard([("personal_value", "Bruno Exemplo")])
    assert (
        guard.check({"m": "Requerido por {{v:id.requerente.nome}}, NIF {{v:id.requerente.nif}}."})
        == []
    )


def test_the_guard_blocks_the_personal_values_of_the_projects_ficha(api: Api, db: Session) -> None:
    project_id = load_confirmed(api, "R1")
    p = db.get(Project, project_id)
    assert p is not None
    p.llm_allowed = True
    terms = terms_for(db, p.id)
    requerente = next(v for k, v in terms if k == "personal_value" and "Exemplo" in v)
    fake = FakeProvider(['{"text": "x"}'])
    c, _ = client(fake)

    with pytest.raises(PrivacyBlocked) as blocked:
        ask(c, db, p, f"A obra é requerida por {requerente.upper()}.")  # also in other cases

    assert {f.kind for f in blocked.value.findings} == {"personal_value"}
    assert fake.sent == []


def test_the_guard_blocks_the_team_names_left_in_the_fixtures(db: Session) -> None:
    if not have_fixtures():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    assert seed_blocked_terms(db, FIXTURES, ("R1", "R2")) >= 2
    names = sorted(names_in(FIXTURES, "R2"))
    fake = FakeProvider(['{"text": "x"}'])
    c, _ = client(fake)

    for name in names:
        with pytest.raises(PrivacyBlocked) as blocked:
            ask(c, db, project(db), f"Projeto elaborado por {name}, engenheiro.")
        assert {f.kind for f in blocked.value.findings} >= {"blocked_name"}
    assert fake.sent == []
    assert seed_blocked_terms(db, FIXTURES, ("R1", "R2")) == seed_blocked_terms(
        db, FIXTURES, ("R1",)
    )


def test_the_technicians_profile_is_blocked(db: Session) -> None:
    fake = FakeProvider(['{"text": "x"}'])
    c, _ = client(fake)
    p = project(db)

    with pytest.raises(PrivacyBlocked):
        c.generate(db, project=p, purpose="drafting", prompt_version="t", system="S",
                   messages=[Message("user", "Assinado por Maria Técnica")], schema=Answer,
                   profile={"tec.nome": "Maria Técnica"})  # fmt: skip


# ---------------------------------------------------------------- validation and retries


def test_invalid_json_is_retried_once_with_the_error(db: Session) -> None:
    fake = FakeProvider(['{"texto": "sem o campo"}', '{"text": "agora sim"}'])
    c, _ = client(fake)

    answer, call = ask(c, db, project(db))

    assert answer.text == "agora sim"
    assert call.status == "ok" and call.attempts == 2
    retry = fake.sent[1][1]
    assert retry[-2] == Message("model", '{"texto": "sem o campo"}')
    assert "text: Field required" in retry[-1].text


def test_invalid_twice_fails_with_our_message(db: Session) -> None:
    fake = FakeProvider(["não é JSON", '{"texto": 1}'])
    c, _ = client(fake)

    with pytest.raises(LlmFailed, match="Resposta do LLM inválida"):
        ask(c, db, project(db))

    call = db.scalars(select(LlmCall)).one()
    assert call.status == "invalid" and "não é JSON" not in (call.error or "")


def test_429_and_503_are_retried_with_exponential_backoff(db: Session) -> None:
    fake = FakeProvider(
        [ProviderError("quota", 429), ProviderError("sobrecarga", 503), '{"text": "ok"}']
    )
    queued: list[float] = []
    c, waits = client(fake, on_wait=queued.append)

    answer, call = ask(c, db, project(db))

    assert answer.text == "ok" and call.attempts == 3
    assert waits == [1.0, 2.0] and queued == [1.0, 2.0]  # "em fila" for the interface


def test_other_errors_and_too_many_retries_fail(db: Session) -> None:
    c, _ = client(FakeProvider([ProviderError("pedido inválido", 400)]))
    with pytest.raises(LlmFailed, match="O LLM não respondeu"):
        ask(c, db, project(db))
    c, waits = client(FakeProvider([ProviderError("q", 429)] * 3))
    with pytest.raises(LlmFailed):
        ask(c, db, project(db))
    assert waits == [1.0, 2.0]  # llm_max_retries = 2


def test_the_model_comes_only_from_the_settings(db: Session) -> None:
    c = LlmClient(FakeProvider(), MemoryRateLimiter(9, 9), Settings(llm_model_drafting=""))
    with pytest.raises(LlmFailed, match="LLM_MODEL_"):
        ask(c, db, project(db))
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiProvider("")
    assert isinstance(make_provider(Settings(llm_provider="fake")), FakeProvider)


def test_llm_call_has_no_column_for_the_content() -> None:
    columns = {c.key for c in inspect(LlmCall).columns}
    assert not {"prompt", "request", "response", "content", "messages", "text"} & columns
    assert {"provider", "model", "purpose", "prompt_version", "input_tokens", "output_tokens",
            "duration_ms", "status"} <= columns  # fmt: skip


# ---------------------------------------------------------------- pace


def test_the_minute_waits_and_the_day_stops() -> None:
    now = [0.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    limiter = MemoryRateLimiter(rpm=2, rpd=3, clock=lambda: now[0], sleep=sleep)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()  # the minute is full: waits for the next one
    assert slept == [60.0]
    with pytest.raises(QuotaExhausted, match="retoma amanhã"):
        limiter.acquire()


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}

    def get(self, key: str) -> int | None:
        return self.data.get(key)

    def incr(self, key: str) -> int:
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def expire(self, key: str, seconds: int) -> None:
        pass


def test_the_redis_limiter_is_shared_by_processes() -> None:
    redis = FakeRedis()
    now = [30.0]
    a = RedisRateLimiter(
        redis, rpm=1, rpd=5, clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s)
    )
    b = RedisRateLimiter(
        redis, rpm=1, rpd=5, clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s)
    )
    a.acquire()
    b.acquire()  # the other process sees the same minute
    assert now[0] == 60.0


# ---------------------------------------------------------------- fallback provider


class Alternative(FakeProvider):
    name = "alternativo"


FALLBACK = Settings(
    llm_model_drafting="principal", llm_fallback_provider="alternativo",
    llm_fallback_model_drafting="modelo-alternativo", llm_max_retries=1, llm_backoff_s=1.0,
)  # fmt: skip


def with_fallback(main: FakeProvider, other: FakeProvider) -> tuple[LlmClient, list[float]]:
    waits: list[float] = []

    def limiter() -> MemoryRateLimiter:
        return MemoryRateLimiter(rpm=100, rpd=100, sleep=lambda s: None)

    c = LlmClient(main, limiter(), FALLBACK, sleep=waits.append, fallback=other,
                  fallback_limiter=limiter())  # fmt: skip
    return c, waits


def test_a_503_that_stays_goes_to_the_fallback(db: Session) -> None:
    other = Alternative(['{"text": "da alternativa"}'])
    c, _ = with_fallback(FakeProvider([ProviderError("sobrecarga", 503)] * 2), other)

    answer, call = ask(c, db, project(db))

    assert answer.text == "da alternativa"
    assert (call.provider, call.model, call.status) == ("alternativo", "modelo-alternativo", "ok")
    assert call.attempts == 3  # 2 on the main one (1 retry), 1 on the fallback
    assert other.sent[0][0] == "Sistema"  # the same request, after the guard


def test_a_quota_429_does_not_switch_provider(db: Session) -> None:
    other = Alternative(['{"text": "não devia"}'])
    c, _ = with_fallback(FakeProvider([ProviderError("quota", 429)] * 2), other)

    with pytest.raises(LlmFailed):
        ask(c, db, project(db))
    assert other.sent == []


def test_the_second_attempt_of_the_validation_stays_on_the_fallback(db: Session) -> None:
    main = FakeProvider([ProviderError("sobrecarga", 503)] * 2)
    other = Alternative(['{"texto": "sem o campo"}', '{"text": "corrigido"}'])
    c, _ = with_fallback(main, other)

    answer, call = ask(c, db, project(db))

    assert answer.text == "corrigido" and call.provider == "alternativo"
    assert len(main.sent) == 2 and len(other.sent) == 2


def test_both_down_fails_with_our_message(db: Session) -> None:
    c, _ = with_fallback(FakeProvider([ProviderError("sobrecarga", 503)] * 2),
                         Alternative([ProviderError("também", 503)] * 2))  # fmt: skip
    with pytest.raises(LlmFailed, match="também o alternativo"):
        ask(c, db, project(db))


def test_the_wait_follows_the_retry_after_of_the_provider(db: Session) -> None:
    fake = FakeProvider([ProviderError("tokens por minuto", 429, retry_after_s=42.0),
                         '{"text": "ok"}'])  # fmt: skip
    c, waits = client(fake)

    ask(c, db, project(db))

    assert waits == [42.0]
