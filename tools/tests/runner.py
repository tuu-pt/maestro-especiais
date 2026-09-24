"""Shared helpers for the anonymizer tests."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from anonymizer.project import ProjectOutcome
from anonymizer.pseudonyms import PseudonymMap


@dataclass
class Run:
    outcome: ProjectOutcome
    mapping: PseudonymMap
    private: Path
    fixtures: Path

    def output(self, name_part: str) -> Path:
        matches = [p for p in self.fixtures.rglob("*") if p.is_file() and name_part in p.name]
        assert len(matches) == 1, (name_part, matches)
        return matches[0]


Runner = Callable[..., Run]
