"""Groq through its OpenAI-compatible HTTP API (SPEC 6.1), for evaluation [A CONFIRMAR: D5, D10].

No SDK: one POST to /chat/completions with httpx. The JSON schema goes in response_format
(structured outputs); a model without it gets JSON mode with the schema in the system prompt.
Model names come only from the environment.
"""

import json
from typing import Any, Literal

import httpx

from app.llm.provider import Message, ProviderError, RawResponse

URL = "https://api.groq.com/openai/v1/chat/completions"
ROLES = {"user": "user", "model": "assistant"}


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("retry-after", ""))
    except ValueError:
        return None


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, timeout_s: float = 60.0,
                 transport: httpx.BaseTransport | None = None) -> None:  # fmt: skip
        if not api_key:
            raise ProviderError("GROQ_API_KEY não está definida.")
        self._client = httpx.Client(
            timeout=timeout_s, transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )  # fmt: skip

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        try:
            return self._client.post(URL, json=payload)
        except httpx.HTTPError as exc:  # network, timeout
            raise ProviderError(f"Falha de ligação à Groq ({type(exc).__name__}).", 503) from None

    def generate(
        self, *, model: str, system: str, messages: list[Message],
        json_schema: dict[str, Any], temperature: float,
    ) -> RawResponse:  # fmt: skip
        chat = [{"role": ROLES[m.role], "content": m.text} for m in messages]
        payload: dict[str, Any] = {
            "model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, *chat],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "saida", "schema": json_schema}},
        }  # fmt: skip
        response = self._post(payload)
        if response.status_code == 400 and "response_format" in response.text:
            # this model has no structured outputs: JSON mode, with the schema in the system prompt
            schema = json.dumps(json_schema, ensure_ascii=False)
            payload["messages"][0] = {"role": "system", "content": f"{system}\n\nEsquema JSON "
                                      f"obrigatório da resposta:\n{schema}"}  # fmt: skip
            payload["response_format"] = {"type": "json_object"}
            response = self._post(payload)
        if response.status_code != 200:  # the body may quote the request: keep only the code
            raise ProviderError(f"Groq respondeu com o código {response.status_code}.",
                                response.status_code, _retry_after(response))  # fmt: skip
        body = response.json()
        usage = body.get("usage") or {}
        return RawResponse(
            text=body["choices"][0]["message"].get("content") or "", model=model,
            input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
        )  # fmt: skip

    def embed(self, texts: list[str], *, model: str, task: Literal["document", "query"]
              ) -> list[list[float]]:  # fmt: skip
        raise ProviderError("A Groq não tem embeddings: use o Gemini (D3).")
