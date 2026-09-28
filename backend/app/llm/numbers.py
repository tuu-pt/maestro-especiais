"""NUM-01 (SPEC 8.4): a digit the LLM wrote outside a placeholder and outside the whitelist."""

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.library import privacy

PLACEHOLDER = re.compile(r"\{\{v:[a-z0-9_.]+\}\}")
WHITELIST = Path(__file__).resolve().parent / "whitelist.yaml"


@lru_cache
def patterns() -> tuple[re.Pattern[str], ...]:
    data = yaml.safe_load(WHITELIST.read_text(encoding="utf-8"))
    return tuple(re.compile(p, re.I) for p in data["patterns"])


def stray_numbers(text: str) -> list[str]:
    """Snippets around each number that should have been a placeholder (masked for display)."""
    bare = PLACEHOLDER.sub(lambda m: " " * len(m.group(0)), text)
    for pattern in patterns():
        bare = pattern.sub(lambda m: " " * len(m.group(0)), bare)
    found = []
    for m in re.finditer(r"\d+(?:[.,]\d+)*", bare):
        left, right = max(0, m.start() - 30), min(len(text), m.end() + 30)
        found.append(privacy.mask(text[left:right].strip()))
    return found
