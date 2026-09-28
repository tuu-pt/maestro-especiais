"""Versioned prompts (SPEC 8.4): <name>_v<n>.md. The version goes to every LlmCall."""

from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTIVE = "adaptive_block_v1"
REWRITE = "rewrite_v1"


@lru_cache
def load(name: str) -> str:
    return (HERE / f"{name}.md").read_text(encoding="utf-8")
