"""Fixtures-only check (CI): pattern detectors, without the correspondence table.

Pseudonyms use reserved formats, so any NIF, phone, email, postal code, coordinate,
DGEG/OET number or address still found here is real. Confirmed false positives are
read, as hashes, from the .pii-allowlist.json next to each project.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from anonymizer.engine import Allowlist, TextAnonymizer
from anonymizer.findings import Finding, UnreadableFileError
from anonymizer.project import ALLOWLIST_FILE, HANDLERS
from anonymizer.pseudonyms import PseudonymMap

_TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
_IGNORED = {".gitkeep", ALLOWLIST_FILE}


@dataclass
class CheckResult:
    files: int
    findings: list[tuple[str, Finding]]

    @property
    def errors(self) -> list[tuple[str, Finding]]:
        return [(p, f) for p, f in self.findings if f.severity == "error"]


def _allowlist_for(path: Path, root: Path) -> Allowlist:
    hashes: set[str] = set()
    for folder in [path.parent, *path.parent.parents]:
        candidate = folder / ALLOWLIST_FILE
        if candidate.exists():
            hashes |= set(json.loads(candidate.read_text(encoding="utf-8")))
        if folder == root:
            break
    return Allowlist(hashes=hashes)


def check_tree(root: Path) -> CheckResult:
    findings: list[tuple[str, Finding]] = []
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name not in _IGNORED)
    for path in files:
        rel = path.relative_to(root).as_posix()
        checker = TextAnonymizer(PseudonymMap(), allowlist=_allowlist_for(path, root))
        for r in checker.residuals(rel):
            if r.severity == "error":
                findings.append((rel, Finding("residual", "nome do ficheiro", r.kind)))
        handler = HANDLERS.get(path.suffix.lower())
        try:
            if handler is not None:
                found = handler.scan_file(path, checker)
            elif path.suffix.lower() in _TEXT_EXTENSIONS:
                text = path.read_text(encoding="utf-8", errors="replace")
                found = [
                    Finding("residual" if r.severity == "error" else "possible_name", "", r.kind)
                    for r in checker.residuals(text)
                ]
            else:
                found = [Finding("unverifiable")]
        except UnreadableFileError:
            found = [Finding("unverifiable")]
        # Values are dropped here: the check output goes to CI logs.
        findings += [(rel, Finding(f.code, f.where, f.kind, f.count)) for f in found]
    return CheckResult(len(files), findings)


def render_check(result: CheckResult, root: Path) -> str:
    from anonymizer.report import MAX_LINES_PER_SECTION, _describe

    lines = [f"Verificação de dados pessoais em {root} · {result.files} ficheiros"]
    errors = result.errors
    for rel, f in errors[:MAX_LINES_PER_SECTION]:
        lines.append(
            f"  ERRO · {rel}" + (f" · {f.where}" if f.where else "") + f" · {_describe(f)}"
        )
    if len(errors) > MAX_LINES_PER_SECTION:
        lines.append(f"  … e mais {len(errors) - MAX_LINES_PER_SECTION}")
    warnings = [x for x in result.findings if x[1].severity == "warning"]
    if warnings:
        lines.append(f"  Avisos (não bloqueiam): {len(warnings)}")
    lines.append("Resultado: " + ("sem dados pessoais detetados." if not errors else "FALHOU."))
    return "\n".join(lines)
