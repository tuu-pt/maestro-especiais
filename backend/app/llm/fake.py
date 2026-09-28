"""A provider for tests and offline development (LLM_PROVIDER=fake). It never uses the network.

With queued responses it returns them in order (tests); with none, it answers an adaptive block
request with the first source's text, as the contract of SPEC 8.4 asks (for the journey without
a key). It records what it was sent so that tests can check the privacy guard came first.
"""

import json
from collections.abc import Callable
from typing import Any, Literal

from app.llm.provider import Message, ProviderError, RawResponse


class FakeProvider:
    name = "fake"

    def __init__(self, responses: list[str | ProviderError] | None = None,
                 answer: Callable[[str, list[Message]], str] | None = None) -> None:  # fmt: skip
        self.responses = list(responses or [])
        self.answer = answer or echo_first_source
        self.sent: list[tuple[str, list[Message]]] = []

    def generate(
        self, *, model: str, system: str, messages: list[Message],
        json_schema: dict[str, Any], temperature: float,
    ) -> RawResponse:  # fmt: skip
        self.sent.append((system, list(messages)))
        if self.responses:
            next_ = self.responses.pop(0)
            if isinstance(next_, ProviderError):
                raise next_
            return RawResponse(next_, model, 10, 10)
        return RawResponse(self.answer(system, messages), model, 10, 10)

    def embed(self, texts: list[str], *, model: str, task: Literal["document", "query"]
              ) -> list[list[float]]:  # fmt: skip
        return [[float(len(t))] for t in texts]


def echo_first_source(system: str, messages: list[Message]) -> str:
    """A valid answer to an adaptive request: the first source's paragraphs, with its id."""
    try:
        request = json.loads(messages[-1].text)
    except (ValueError, IndexError):
        return "{}"
    sources = request.get("sources") or []
    first = sources[0] if sources else {"id": "", "text": ""}
    paragraphs = [
        {"id": f"p{i}", "text": line, "sources": [first["id"]] if first["id"] else []}
        for i, line in enumerate((first.get("text") or "").split("\n"), start=1)
        if line.strip()
    ]
    return json.dumps({"block_key": request.get("block_key", ""), "paragraphs": paragraphs,
                       "missing_data": [], "assumptions": []}, ensure_ascii=False)  # fmt: skip
