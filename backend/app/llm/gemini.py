"""Gemini through the google-genai SDK (SPEC 6.1). Model names come only from the environment."""

from typing import Any, Literal, cast

import httpx

from app.llm.provider import Message, ProviderError, RawResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, timeout_s: float = 60.0) -> None:
        if not api_key:
            raise ProviderError("GEMINI_API_KEY não está definida.")
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    def generate(
        self, *, model: str, system: str, messages: list[Message],
        json_schema: dict[str, Any], temperature: float,
    ) -> RawResponse:  # fmt: skip
        from google.genai import errors

        types = self._types
        contents = [
            types.Content(role=m.role, parts=[types.Part.from_text(text=m.text)]) for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system, temperature=temperature,
            response_mime_type="application/json", response_json_schema=json_schema,
        )  # fmt: skip
        try:
            response = self._client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except errors.APIError as exc:  # the message may quote the request: keep only the code
            raise ProviderError(f"Gemini respondeu com o código {exc.code}.", exc.code) from None
        except (httpx.HTTPError, TimeoutError, OSError) as exc:  # network, timeout
            raise ProviderError(
                f"Falha de ligação ao Gemini ({type(exc).__name__}).", 503
            ) from None
        usage = response.usage_metadata
        return RawResponse(
            text=response.text or "", model=model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
        )  # fmt: skip

    def embed(self, texts: list[str], *, model: str, task: Literal["document", "query"]
              ) -> list[list[float]]:  # fmt: skip
        types = self._types
        kind = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        result = self._client.models.embed_content(
            model=model,
            contents=cast("Any", texts),
            config=types.EmbedContentConfig(task_type=kind),
        )
        return [list(e.values or []) for e in result.embeddings or []]
