"""Anonymize one reference project: harvest, transform into staging, verify, promote.

Fixtures are replaced only when verification finds no residual personal data; otherwise
the previous fixtures stay untouched.
"""

import fnmatch
import json
import shutil
import traceback
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

import yaml

from anonymizer import ooxml, pdf, xls
from anonymizer.detectors import detect
from anonymizer.engine import Allowlist, Seed, TextAnonymizer, value_hash
from anonymizer.findings import Finding, UnreadableFileError
from anonymizer.harvest import dedupe, seeds_from_lines
from anonymizer.pseudonyms import PseudonymMap
from anonymizer.textnorm import fold_simple

HANDLERS: dict[str, ModuleType] = {
    ext: module for module in (ooxml, xls, pdf) for ext in module.EXTENSIONS
}
ALLOWLIST_FILE = ".pii-allowlist.json"


@dataclass
class Overrides:
    """data/private/anonymize_overrides.yaml: what a person adds or confirms."""

    seeds: list[Seed] = field(default_factory=list)
    allow: Allowlist = field(default_factory=Allowlist)
    allow_items: list[tuple[str, str]] = field(default_factory=list)
    strip_images: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Overrides":
        if not path.exists():
            return cls()
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        allow_items = [(str(a["kind"]), str(a["value"])) for a in data.get("allow") or []]
        return cls(
            seeds=[Seed(str(s["kind"]), str(s["value"])) for s in data.get("seeds") or []],
            allow=Allowlist.from_items(allow_items),
            allow_items=allow_items,
            strip_images=[str(g) for g in data.get("strip_images") or []],
        )


@dataclass
class FileOutcome:
    output: str  # anonymized relative path: safe to print
    findings: list[Finding]
    copied: bool


@dataclass
class ProjectOutcome:
    code: str
    files: list[FileOutcome]
    promoted: bool

    @property
    def errors(self) -> list[tuple[str, Finding]]:
        return [(f.output, x) for f in self.files for x in f.findings if x.severity == "error"]


def anonymize_path(rel: PurePosixPath, engine: TextAnonymizer) -> PurePosixPath:
    """Relative path with personal data removed from folder and file names."""
    parts = []
    for i, part in enumerate(rel.parts):
        is_file = i == len(rel.parts) - 1
        stem, suffix = (
            (PurePosixPath(part).stem, PurePosixPath(part).suffix) if is_file else (part, "")
        )
        new = engine.anonymize(stem)[0]
        if " " not in stem:
            new = new.replace(" ", "_")
        parts.append(new + suffix)
    return PurePosixPath(*parts)


def _unique(path: PurePosixPath, taken: set[PurePosixPath]) -> PurePosixPath:
    candidate, n = path, 2
    while candidate in taken:
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        n += 1
    taken.add(candidate)
    return candidate


def _log_error(log: Path, stage: str, index: int) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"--- {stage} · ficheiro #{index}\n{traceback.format_exc()}\n")


def run_project(
    code: str,
    source: Path,
    staging: Path,
    target: Path,
    mapping: PseudonymMap,
    overrides: Overrides,
    error_log: Path,
) -> ProjectOutcome:
    files = sorted(
        p for p in source.rglob("*") if p.is_file() and not p.name.startswith(("~$", "."))
    )

    # 1. Harvest known values from every readable file.
    seeds: list[Seed] = list(overrides.seeds)
    local: dict[Path, list[Seed]] = {}
    forms: set[Path] = set()
    early: dict[Path, list[Finding]] = {}
    unreadable: dict[Path, str] = {}
    for i, path in enumerate(files):
        handler = HANDLERS.get(path.suffix.lower())
        if handler is None:
            continue
        try:
            found, notes, is_form = handler.harvest(path)
            texts = handler.texts(path)
        except UnreadableFileError as exc:
            unreadable[path] = exc.code
            continue
        except Exception:  # noqa: BLE001 - corrupted file: never copied, reported
            _log_error(error_log, "harvest", i)
            unreadable[path] = "unreadable"
            continue
        early[path] = notes
        if is_form:
            forms.add(path)
        for _, text in texts:
            found += seeds_from_lines(text)
            found += [
                Seed("name", d.value)
                for d in detect(text)
                if d.kind == "name" and len(d.value.split()) >= 2
            ]
        local[path] = [s for s in dedupe(found) if s.local]
        seeds += [s for s in found if not s.local]
    engine = TextAnonymizer(mapping, dedupe(seeds), overrides.allow)

    # 2. Transform into staging.
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    outcomes: list[FileOutcome] = []
    staged: list[tuple[Path, Path, FileOutcome]] = []
    taken: set[PurePosixPath] = set()
    for i, path in enumerate(files):
        rel = PurePosixPath(path.relative_to(source).as_posix())
        out_rel = _unique(anonymize_path(rel, engine), taken)
        handler = HANDLERS.get(path.suffix.lower())
        if handler is None:
            outcomes.append(FileOutcome(str(out_rel), [Finding("unsupported")], copied=False))
            continue
        if path in unreadable:
            outcomes.append(FileOutcome(str(out_rel), [Finding(unreadable[path])], copied=False))
            continue
        destination = staging / out_rel
        strip = path in forms or any(fnmatch.fnmatch(str(rel), g) for g in overrides.strip_images)
        try:
            found = handler.transform_file(
                path, destination, engine.with_local_seeds(local.get(path, [])), strip
            )
        except Exception:  # noqa: BLE001
            _log_error(error_log, "transform", i)
            destination.unlink(missing_ok=True)
            outcomes.append(FileOutcome(str(out_rel), [Finding("internal_error")], copied=False))
            continue
        outcome = FileOutcome(str(out_rel), early.get(path, []) + found, copied=True)
        outcomes.append(outcome)
        staged.append((path, destination, outcome))

    # 3. Verify the staged output against every real value in the table.
    checker = TextAnonymizer.for_verification(mapping, overrides.allow)
    for i, (path, destination, outcome) in enumerate(staged):
        file_checker = checker.with_local_seeds(local.get(path, []))
        for residual in file_checker.residuals(outcome.output):
            outcome.findings.append(
                Finding("residual", "nome do ficheiro", residual.kind, original=residual.value)
            )
        try:
            outcome.findings += HANDLERS[path.suffix.lower()].scan_file(destination, file_checker)
        except Exception:  # noqa: BLE001
            _log_error(error_log, "verify", i)
            outcome.findings.append(Finding("internal_error", "verificação"))

    result = ProjectOutcome(code, outcomes, promoted=False)
    # Nothing anonymized (empty folder, only archives or unsupported files): keep the old fixtures.
    if not result.errors and staged:
        _write_allowlist(staging, overrides.allow_items)
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), str(target))
        result.promoted = True
    return result


def _write_allowlist(folder: Path, items: list[tuple[str, str]]) -> None:
    """Confirmed false positives as hashes, so the CI check can skip them without values."""
    if not items:
        return
    entries = sorted({f"{kind}:{value_hash(fold_simple(value))}" for kind, value in items})
    (folder / ALLOWLIST_FILE).write_bytes(json.dumps(entries, indent=1).encode("utf-8"))
