"""Personal values out of what people and logs see (SPEC 12, P9; Phase 5).

The written pieces made by hand have the requerente and the technician in the clear. What the
screens show of them (the read-only sections, the evidence of an issue) passes here: the known
personal values of the project (ficha-base, cover and signature of the piece, the technician's
profile) and the patterns of app/library/privacy are replaced by •••. Comparisons are made on
the real values, in the backend, before this.
"""

import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.library import privacy
from app.models import FichaRevision, FichaValue
from app.validation.pieces import MASK

MIN_LENGTH = 3  # shorter values are too common to be masked without masking ordinary words


class Masker:
    def __init__(self, values: Iterable[str] = ()) -> None:
        self._values: set[str] = set()
        self._pattern: re.Pattern[str] | None = None
        self.add(values)

    def add(self, values: Iterable[str]) -> None:
        for v in values:
            v = " ".join(str(v).split())
            if len(v) >= MIN_LENGTH:
                self._values.add(v)
        self._pattern = None

    def _compiled(self) -> re.Pattern[str] | None:
        if self._pattern is None and self._values:
            parts = sorted(self._values, key=len, reverse=True)
            words = [r"\s*".join(re.escape(w) for w in v.split()) for v in parts]
            self._pattern = re.compile(r"(?<!\w)(?:" + "|".join(words) + r")(?!\w)", re.I)
        return self._pattern

    def __call__(self, text: str) -> str:
        pattern = self._compiled()
        masked = pattern.sub(MASK, text) if pattern else text
        return privacy.mask(masked)


def project_personal_values(db: Session, project_id: uuid.UUID) -> list[str]:
    """Every personal value of the ficha-base of the project, in any revision."""
    rows = db.scalars(
        select(FichaValue.value)
        .join(FichaRevision, FichaValue.revision_id == FichaRevision.id)
        .where(FichaRevision.project_id == project_id, FichaValue.personal_data.is_(True))
    ).all()
    out = []
    for value in rows:
        if isinstance(value, list):
            out += [str(v) for v in value if v not in (None, "")]
        elif value not in (None, ""):
            out.append(str(value))
    return out
