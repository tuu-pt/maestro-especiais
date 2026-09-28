"""GroqProvider (OpenAI-compatible API) without the network: requests, JSON mode, errors."""

import json
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.llm.client import make_provider
from app.llm.groq import GroqProvider
from app.llm.provider import Message, ProviderError

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def provider(handler: Any) -> tuple[GroqProvider, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        response: httpx.Response = handler(request, len(sent))
        return response

    return GroqProvider("chave-de-teste", transport=httpx.MockTransport(record)), sent


def answer(text: str = '{"ok": true}') -> httpx.Response:
    body = {"choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3}}  # fmt: skip
    return httpx.Response(200, json=body)


def generate(p: GroqProvider) -> Any:
    return p.generate(model="modelo-de-teste", system="Regras.", json_schema=SCHEMA,
                      messages=[Message("user", "Olá"), Message("model", "Antes")],
                      temperature=0.2)  # fmt: skip


def test_sends_the_schema_and_maps_the_roles() -> None:
    p, sent = provider(lambda request, n: answer())

    result = generate(p)

    assert result.text == '{"ok": true}' and (result.input_tokens, result.output_tokens) == (12, 3)
    [payload] = sent
    assert payload["model"] == "modelo-de-teste"
    assert [m["role"] for m in payload["messages"]] == ["system", "user", "assistant"]
    assert payload["response_format"]["json_schema"]["schema"] == SCHEMA


def test_a_model_without_structured_outputs_gets_json_mode() -> None:
    def handler(request: httpx.Request, n: int) -> httpx.Response:
        if n == 1:
            return httpx.Response(400, json={"error": {"message": "response_format not supported"}})
        return answer()

    p, sent = provider(handler)

    assert generate(p).text == '{"ok": true}'
    assert sent[1]["response_format"] == {"type": "json_object"}
    assert '"ok"' in sent[1]["messages"][0]["content"]  # the schema is in the system prompt


@pytest.mark.parametrize(("status", "retryable"), [(429, True), (503, True), (401, False)])
def test_errors_keep_only_the_code(status: int, retryable: bool) -> None:
    p, _ = provider(lambda request, n: httpx.Response(status, text="pedido citado: Olá"))

    with pytest.raises(ProviderError) as error:
        generate(p)

    assert error.value.retryable is retryable and "Olá" not in str(error.value)


def test_make_provider_picks_groq() -> None:
    assert make_provider(Settings(llm_provider="groq", groq_api_key="x")).name == "groq"
    with pytest.raises(ProviderError):
        make_provider(Settings(llm_provider="groq"))
