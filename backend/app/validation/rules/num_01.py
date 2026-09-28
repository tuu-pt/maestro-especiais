"""NUM-01 (SPEC 8.4, 9): a number in the agent's text outside a placeholder and the whitelist.

The drafting flags it when the proposal arrives (Phase 4); the validation flags it again on the
text of the agent that is in the pieces. Only the agent's text: in text written by people the
numbers are theirs (D-d, [A CONFIRMAR]). Numbers copied from the sources (regulatory distances)
are flagged too, for the technician to confirm: the rule is not relaxed.
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.library import privacy
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, Finding, Rule

PLACEHOLDER = re.compile(r"\{\{v:[a-z0-9_.]+\}\}")
WHITELIST = Path(__file__).resolve().parents[2] / "llm" / "whitelist.yaml"
MESSAGE = "Número fora de marcador: confirmar ou trocar por um valor da ficha."


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


def check(ctx: Context) -> list[Finding]:
    out = []
    for p in ctx.paragraphs("MDJ", "CTE"):
        if not p.generated:
            continue
        piece = ctx.pieces[p.piece]
        for n, snippet in enumerate(stray_numbers(p.source_text or p.text)):
            out.append(RULE.finding(
                f"{piece.name} · {p.section_title}: {MESSAGE}",
                key=f"{p.piece}|{p.section_key}|{p.index}|{n}",
                location={"piece": p.piece, "section": p.section_key,
                          "section_title": p.section_title, "section_id": p.section_id,
                          "paragraph": p.index, "anchor": p.anchor},
                evidence={"excerpt": snippet},
                likely_reading="Número escrito pelo agente sem origem na ficha-base.",
                suggested_fix="Trocar por um valor da ficha ou confirmar a fonte.",
                actions=[OPEN_EDITOR],
            ))  # fmt: skip
    return out


RULE = Rule("NUM-01", "references", "critical", "Número no texto sem origem", check)
