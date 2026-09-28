"""Acceptance of Phase 5: the 14 cases of Annex C in R1 and R2, with the likely reading, and the
controls without alerts. With --annex-c-report=<path> it also writes docs/fase5-anexo-c.md."""

import json
from pathlib import Path
from typing import Any

import pytest
from audit_projects import audited
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FichaValue, PieceFacts
from app.validation.annex_c import CASES, control_alerts, evaluate, markdown

pytestmark = pytest.mark.usefixtures("inline_ingestion")
__all__ = ["audited"]


def personal_values(db: Session) -> set[str]:
    values = {str(v).lower() for v in db.scalars(select(FichaValue.value).where(
        FichaValue.personal_data.is_(True))) if isinstance(v, str) and len(v) > 5}  # fmt: skip
    for cached in db.scalars(select(PieceFacts)):
        values |= {str(f["value"]).lower() for f in cached.data["facts"]
                   if f["personal"] and len(str(f["value"])) > 5}  # fmt: skip
    return values


def test_every_case_of_annex_c_is_found_with_its_likely_reading(
    audited: Any, db: Session, request: pytest.FixtureRequest
) -> None:
    states = {"R1": audited("R1")[1], "R2": audited("R2")[1],
              "R1-CCP": audited("R1", public=True)[1]}  # fmt: skip

    results = evaluate(states)
    report = markdown(states)

    missing = [(r.case.id, r.found) for r in results if not r.detected]
    wrong = [(r.case.id, r.reading, r.case.expected) for r in results if not r.reading_ok]
    assert len(results) == len(CASES) == 14
    assert not missing and not wrong, (missing, wrong)
    assert all(not alerts for _, alerts in control_alerts(states))
    shown = (report + json.dumps(states, ensure_ascii=False)).lower()
    assert not [v for v in personal_values(db) if v in shown]
    path = request.config.getoption("--annex-c-report")
    if path:
        Path(path).write_text(report, encoding="utf-8")
