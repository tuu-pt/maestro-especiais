"""Claude through the official Anthropic SDK (SPEC 6.1), the third provider (8 Oct 2026).

One request to the Messages API with the JSON schema in `output_config.format` (structured
outputs). A schema the API does not take gets the schema in the system prompt instead (Pydantic
still validates the answer in app.llm.client). No sampling parameters: the current models refuse
`temperature`. The SDK's own retries are off: retries, pace and the change of provider live in
app.llm.client, the same for every provider. Model names come only from the environment.
"""

import json
from typing import Any, Literal

import anthropic

from app.llm.provider import Message, ProviderError, RawResponse

ROLES = {"user": "user", "model": "assistant"}
MAX_TOKENS = 16000


def _strict(schema: Any) -> Any:
    """Structured outputs ask every object for `additionalProperties: false`."""
    if isinstance(schema, dict):
        out = {k: _strict(v) for k, v in schema.items()}
        if out.get("type") == "object":
            out.setdefault("additionalProperties", False)
        return out
    if isinstance(schema, list):
        return [_strict(v) for v in schema]
    return schema


def _retry_after(exc: anthropic.APIStatusError) -> float | None:
    try:
        return float(exc.response.headers.get("retry-after", ""))
    except ValueError:
        return None


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str, timeout_s: float = 60.0,
                 client: anthropic.Anthropic | None = None) -> None:  # fmt: skip
        if client is None and not api_key:
            raise ProviderError("ANTHROPIC_API_KEY não está definida.")
        self._client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout_s,
                                                     max_retries=0)  # fmt: skip

    def _create(self, **kwargs: Any) -> Any:
        try:
            return self._client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:  # the body may quote the request: keep the code
            raise ProviderError(f"Claude respondeu com o código {exc.status_code}.",
                                exc.status_code, _retry_after(exc)) from None  # fmt: skip
        except anthropic.APIConnectionError as exc:  # network and timeout
            raise ProviderError(f"Falha de ligação ao Claude ({type(exc).__name__}).",
                                503) from None  # fmt: skip

    def generate(
        self, *, model: str, system: str, messages: list[Message],
        json_schema: dict[str, Any], temperature: float,
    ) -> RawResponse:  # fmt: skip
        chat = [{"role": ROLES[m.role], "content": m.text} for m in messages]
        request: dict[str, Any] = {"model": model, "max_tokens": MAX_TOKENS, "system": system,
                                   "messages": chat}  # fmt: skip
        try:
            response = self._create(**request, output_config={
                "format": {"type": "json_schema", "schema": _strict(json_schema)}})  # fmt: skip
        except ProviderError as exc:
            if exc.status != 400:
                raise
            # a schema structured outputs does not take: the schema in the system prompt
            schema = json.dumps(json_schema, ensure_ascii=False)
            request["system"] = (f"{system}\n\nResponde só com JSON que cumpra este esquema:\n"
                                 f"{schema}")  # fmt: skip
            response = self._create(**request)
        if response.stop_reason == "refusal":
            raise ProviderError("O Claude recusou o pedido.", 422)
        text = "".join(b.text for b in response.content if b.type == "text")
        return RawResponse(text=text, model=model, input_tokens=response.usage.input_tokens,
                           output_tokens=response.usage.output_tokens)  # fmt: skip

    def embed(self, texts: list[str], *, model: str, task: Literal["document", "query"]
              ) -> list[list[float]]:  # fmt: skip
        raise ProviderError("O Claude não tem embeddings: use o Gemini (D3).")
