"""Rules and what they find (SPEC 9). Deterministic: no LLM, nothing computed, nothing applied.

A rule reads the context of one validation run (the confirmed ficha-base, the pieces and the
facts read from them) and returns findings. A finding says what was found, where, the evidence
(masked: never a personal value), the likely reading and the actions a person may take. The
engine turns findings into ValidationIssue rows; nothing is ever corrected by a rule.
"""

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from app.validation.context import Context

Severity = Literal["critical", "warning", "info"]

CATEGORIES = {
    "references": "Referências",
    "coherence": "Coerência",
    "drawings": "Peças desenhadas",
    "calculation": "Cálculo (verificação)",
    "procurement": "Contratação",
    "content": "Conteúdo",
    "quality": "Qualidade",
    "equipment": "Fichas técnicas",
}

# What a person can do with an issue (the screen shows the ones that apply)
OPEN_EDITOR = "open_editor"
OPEN_FICHA = "open_ficha"
ASK_CURATOR = "ask_curator"
OPEN_EQUIPMENT = "open_equipment"  # screen F (Phase 7)
CONFIRM_SHEET = "confirm_sheet"
IGNORE = "ignore"


@dataclass
class Finding:
    rule_id: str
    message: str  # PT-PT, without personal values
    key: str  # stable identity within the rule (no personal values): the fingerprint
    severity: Severity | None = None  # None: the rule's default
    location: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)  # masked
    likely_reading: str | None = None
    suggested_fix: str | None = None
    actions: list[str] = field(default_factory=list)

    def fingerprint(self) -> str:
        return hashlib.sha256(f"{self.rule_id}|{self.key}".encode()).hexdigest()


Check = Callable[["Context"], Iterable[Finding]]


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    severity: Severity  # default (SPEC 9); a finding may say otherwise (e.g. COE-06)
    title: str
    check: Check

    def finding(self, message: str, key: str, **kwargs: Any) -> Finding:
        actions = kwargs.pop("actions", None)
        return Finding(self.id, message, key, actions=[*(actions or []), IGNORE], **kwargs)
