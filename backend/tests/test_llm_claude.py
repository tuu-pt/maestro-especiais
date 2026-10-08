"""Claude as the third provider (8 Oct 2026): the request it sends and the errors it maps.

No network: the SDK client is replaced by a recorder.
"""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.config import Settings
from app.llm.claude import ClaudeProvider
from app.llm.client import make_provider
from app.llm.provider import Message, ProviderError

SCHEMA = {"type": "object", "properties": {"text": {"type": "string"},
          "parts": {"type": "array", "items": {"type": "object",
                    "properties": {"k": {"type": "string"}}}}},
          "required": ["text"]}  # fmt: skip


def answer(text: str = '{"text": "ok"}', stop: str = "end_turn") -> Any:
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)],
                           usage=SimpleNamespace(input_tokens=12, output_tokens=5))  # fmt: skip


class Recorder:
    def __init__(self, *results: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self.results = list(results)
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def status_error(code: int, retry_after: str | None = None) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx2.Response(code, headers=headers, request=request)
    return anthropic.APIStatusError("erro com o pedido Olá", response=response, body=None)


def generate(recorder: Recorder) -> Any:
    provider = ClaudeProvider("", client=recorder)  # type: ignore[arg-type]
    return provider.generate(model="claude-modelo", system="Sistema",
                             messages=[Message("user", "Olá"), Message("model", "{}")],
                             json_schema=SCHEMA, temperature=0.2)  # fmt: skip


def test_the_schema_goes_as_structured_output_and_the_roles_are_mapped() -> None:
    recorder = Recorder(answer())

    raw = generate(recorder)

    [sent] = recorder.calls
    assert (raw.text, raw.input_tokens, raw.output_tokens) == ('{"text": "ok"}', 12, 5)
    assert sent["model"] == "claude-modelo" and sent["system"] == "Sistema"
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant"]
    assert "temperature" not in sent  # the current models refuse sampling parameters
    schema = sent["output_config"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["parts"]["items"]["additionalProperties"] is False


def test_a_schema_the_api_refuses_goes_in_the_system_prompt() -> None:
    recorder = Recorder(status_error(400), answer())

    generate(recorder)

    retry = recorder.calls[1]
    assert "output_config" not in retry and '"required": ["text"]' in retry["system"]


@pytest.mark.parametrize(("code", "retryable", "unavailable"),
                         [(429, True, False), (529, True, True), (401, False, False)])  # fmt: skip
def test_errors_keep_only_the_code(code: int, retryable: bool, unavailable: bool) -> None:
    with pytest.raises(ProviderError) as error:
        generate(Recorder(status_error(code, "7")))
    assert (error.value.status, error.value.retryable) == (code, retryable)
    assert error.value.unavailable is unavailable and error.value.retry_after_s == 7.0
    assert "Olá" not in str(error.value)


def test_no_connection_is_an_unavailable_service() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    with pytest.raises(ProviderError) as error:
        generate(Recorder(anthropic.APIConnectionError(request=request)))
    assert error.value.status == 503


def test_a_refusal_is_an_error_of_the_provider() -> None:
    with pytest.raises(ProviderError, match="recusou"):
        generate(Recorder(answer(stop="refusal")))


def test_make_provider_picks_claude() -> None:
    assert make_provider(Settings(llm_provider="claude", anthropic_api_key="x")).name == "claude"
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        make_provider(Settings(llm_provider="claude", anthropic_api_key=""))
