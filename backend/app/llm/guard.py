"""Privacy guard before every request to the LLM (P9): personal data never leaves the backend.

What it looks for, in every part of the request (placeholders {{v:…}} are ignored):
- the personal values of the project's ficha-base (personal_data = true);
- the technician's profile;
- the blocked names (BlockedTerm: TUU team and technicians, e.g. the names left in the
  fixtures by decision of 24 set 2026);
- the patterns of app.library.privacy: emails, NIF, CC, phones, postal codes, DGEG/OET numbers,
  addresses, dates.

Any finding blocks the request. The finding says what kind and where, never the value.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.consolidate import latest_revision
from app.ingest.detect import fold
from app.library import privacy
from app.models import BlockedTerm, FichaValue

PLACEHOLDER = re.compile(r"\{\{v:[a-z0-9_.]+\}\}")
MIN_TERM = 3


@dataclass(frozen=True)
class Finding:
    kind: str  # e.g. "email", "personal_value", "blocked_name"
    where: str  # "system", "message 1"

    def as_json(self) -> dict[str, str]:
        return {"kind": self.kind, "where": self.where}


class PrivacyBlocked(Exception):
    def __init__(self, findings: list[Finding]) -> None:
        kinds = ", ".join(sorted({f.kind for f in findings}))
        super().__init__(f"Pedido ao LLM bloqueado: dados pessoais no pedido ({kinds}).")
        self.findings = findings


@dataclass
class PrivacyGuard:
    terms: list[tuple[str, str]]  # (kind, value)

    def __post_init__(self) -> None:
        self._patterns = [
            (
                kind,
                re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, fold(v).split())) + r"(?!\w)"),
            )
            for kind, v in self.terms
            if len(fold(v)) >= MIN_TERM
        ]

    def check(self, parts: dict[str, str]) -> list[Finding]:
        findings: list[Finding] = []
        for where, text in parts.items():
            bare = PLACEHOLDER.sub(" ", text)
            findings += [Finding(h.kind, where) for h in privacy.find(bare)]
            folded = fold(bare)
            findings += [Finding(kind, where) for kind, p in self._patterns if p.search(folded)]
        return list(dict.fromkeys(findings))

    def enforce(self, parts: dict[str, str]) -> None:
        findings = self.check(parts)
        if findings:
            raise PrivacyBlocked(findings)


def terms_for(db: Session, project_id: uuid.UUID | None,
              profile: dict[str, str] | None = None) -> list[tuple[str, str]]:  # fmt: skip
    terms: list[tuple[str, str]] = [
        ("blocked_name", t.value) for t in db.scalars(select(BlockedTerm))
    ]
    terms += [("profile", v) for v in (profile or {}).values() if v]
    if project_id is not None:
        revision = latest_revision(db, project_id)
        if revision is not None:
            for v in db.scalars(
                select(FichaValue).where(
                    FichaValue.revision_id == revision.id, FichaValue.personal_data.is_(True)
                )
            ):
                if v.value not in (None, ""):
                    terms.append(("personal_value", str(v.value)))
    return terms
