"""The interface every LLM provider implements (SPEC 6.1). No other module imports an SDK.

A provider only sends one request and returns the raw text with its usage; validation, retries,
rate limiting, the privacy guard and the LlmCall record live in app.llm.client, the same for
every provider.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class Message:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class RawResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(Exception):
    """A failed request. retryable for 429 (quota) and 5xx (e.g. 503 overloaded)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.status == 429 or (self.status is not None and self.status >= 500)


class LlmProvider(Protocol):
    name: str

    def generate(
        self, *, model: str, system: str, messages: list[Message],
        json_schema: dict[str, Any], temperature: float,
    ) -> RawResponse: ...  # fmt: skip

    def embed(self, texts: list[str], *, model: str, task: Literal["document", "query"]
              ) -> list[list[float]]: ...  # fmt: skip
