from collections.abc import Callable
from pathlib import Path

import pytest
from runner import Run, Runner

from anonymizer.project import Overrides, run_project
from anonymizer.pseudonyms import PseudonymMap


@pytest.fixture
def run_anonymizer(tmp_path: Path) -> Runner:
    """Build a synthetic project with builder(dir) and anonymize it, all inside tmp_path."""

    def run(
        builder: Callable[[Path], object],
        code: str = "R9",
        mapping: PseudonymMap | None = None,
        overrides: Overrides | None = None,
    ) -> Run:
        private = tmp_path / "private"
        fixtures = tmp_path / "fixtures"
        source = private / code
        if not source.exists():
            builder(source)
        mapping = mapping if mapping is not None else PseudonymMap()
        outcome = run_project(
            code,
            source,
            private / ".staging" / code,
            fixtures / code,
            mapping,
            overrides or Overrides(),
            private / "anonymize_error.log",
        )
        return Run(outcome, mapping, private, fixtures / code)

    return run
