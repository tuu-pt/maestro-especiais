"""Known personal data harvested before anonymizing (SPEC 12.2).

Sources: fixed cells of the DGEG ficha eletrotécnica, label/value tables of the forms
(identificação do projeto, termo de responsabilidade) and "Label: value" lines.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from anonymizer.detectors import ENTITY_WORDS, detect
from anonymizer.engine import Seed
from anonymizer.textnorm import digits_only, fold_simple

MAPS = Path(__file__).parent / "maps"

_NAME_QUALIFIERS = {
    "",
    "completo",
    "do requerente",
    "do promotor",
    "do dono de obra",
    "do tecnico",
    "do tecnico responsavel",
    "do autor",
    "do projetista",
}
_NOT_A_PERSON = re.compile(
    r"(?i)\b(?:moradia|edif[íi]cio|habita[çc][ãa]o|reabilita[çc][ãa]o|constru[çc][ãa]o|"
    r"amplia[çc][ãa]o|obra|projeto|loja|armaz[ée]m|pavilh[ãa]o|instala[çc][ãa]o|"
    r"unifamiliar|multifamiliar|fra[çc][ãa]o|lote|pr[ée]dio)\b"
)


@dataclass(frozen=True)
class FeMap:
    template_version: str
    version_cell: str
    cells: dict[str, str]  # cell -> kind


@cache
def fe_maps() -> tuple[FeMap, ...]:
    maps = []
    for path in sorted(MAPS.glob("fe_*.yaml")):
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        cells = {cell: spec["kind"] for cell, spec in data["cells"].items()}
        maps.append(FeMap(data["template_version"], data["version_cell"], cells))
    return tuple(maps)


@cache
def form_labels() -> tuple[tuple[str, str], ...]:
    """(folded keyword, kind), longest keyword first."""
    data: dict[str, Any] = yaml.safe_load((MAPS / "forms.yaml").read_text(encoding="utf-8"))
    pairs = [(fold_simple(k), kind) for kind, kws in data["labels"].items() for k in kws]
    return tuple(sorted(pairs, key=lambda p: -len(p[0])))


def label_kind(text: str) -> str | None:
    """Kind of personal datum a form label announces, or None if it is not a label."""
    folded = fold_simple(text).rstrip(" :.-–")
    if not folded or len(folded) > 60:
        return None
    for keyword, kind in form_labels():
        if (
            folded == keyword
            or folded.startswith(keyword + " ")
            or folded.startswith(keyword + "(")
        ):
            rest = folded[len(keyword) :].strip(" :()/.-")
            if kind == "name" and rest not in _NAME_QUALIFIERS:
                return None
            if len(rest) > 30:
                return None
            return kind
    return None


def plausible(kind: str, value: str) -> bool:
    """Does value look like a datum of this kind? Filters headers and empty cells."""
    value = value.strip()
    if not value or label_kind(value):
        return False
    digits = digits_only(value)
    if kind == "name":
        tokens = value.split()
        return (
            2 <= len(tokens) <= 8
            and not digits
            and all(t[:1].isalpha() for t in tokens)
            and not ENTITY_WORDS.search(value)
            and not _NOT_A_PERSON.search(value)
        )
    if kind in {"nif", "phone"}:
        return len(digits) in (9, 12, 14)
    if kind == "cc":
        return len(digits) >= 7
    if kind == "dgeg_oet":
        return 3 <= len(digits) <= 7
    if kind == "postal_code":
        return bool(re.search(r"\d{4}-\d{3}", value))
    if kind == "email":
        return "@" in value
    if kind == "address":
        return any(c.isalpha() for c in value) and len(value) >= 6
    return False


def seeds_for(kind: str, value: str) -> list[Seed]:
    """Seeds from a value whose kind is expected. "auto" relies on the detectors."""
    value = value.strip()
    if not value:
        return []
    if kind == "auto":
        return [Seed(d.kind, d.value) for d in detect(value)]
    if kind == "postal_code":
        m = re.search(r"\d{4}-\d{3}", value)
        return [Seed("postal_code", m.group(0))] if m else []
    if not plausible(kind, value):
        return []
    # Short numbers (DGEG/OET) are only replaced in the file they came from.
    local = kind == "dgeg_oet" or (kind in {"cc"} and len(digits_only(value)) < 7)
    return [Seed(kind, value, local=local)]


def seeds_from_grid(rows: Sequence[Sequence[str]]) -> list[Seed]:
    """Label/value pairs in a table: value to the right, or below when the right is empty."""
    seeds: list[Seed] = []
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            kind = label_kind(cell)
            if kind is None:
                continue
            right = next((v for v in row[c + 1 :] if v.strip() and v != cell), "")
            below = rows[r + 1][c] if r + 1 < len(rows) and c < len(rows[r + 1]) else ""
            for candidate in (right, below):
                found = seeds_for(kind, candidate)
                if found:
                    seeds += found
                    break
    return seeds


_LABEL_LINE = re.compile(r"^\s*(?P<label>[^:\n]{2,60}?)\s*:\s*(?P<value>[^\n]{2,120})$", re.M)


def seeds_from_lines(text: str) -> list[Seed]:
    """'Label: value' lines, e.g. 'Requerente: João Almeida' or 'NIF: 123 456 789'."""
    seeds: list[Seed] = []
    for m in _LABEL_LINE.finditer(text):
        kind = label_kind(m.group("label"))
        if kind:
            seeds += seeds_for(kind, m.group("value"))
    return seeds


def dedupe(seeds: Iterable[Seed]) -> list[Seed]:
    return list(dict.fromkeys(seeds))
