"""Legacy .xls (BIFF) anonymization: read with xlrd, rewrite with xlutils/xlwt.

Formulas become their cached values (Phase 0 decision): the 09-Folhas de Cálculo are
only read by value. Cell styles are kept. Document properties are not carried over.
"""

from pathlib import Path
from typing import Any

import xlrd
from xlutils.copy import copy as xl_copy

from anonymizer.engine import Seed, TextAnonymizer
from anonymizer.findings import Finding
from anonymizer.harvest import dedupe, seeds_from_grid

EXTENSIONS = (".xls",)


def _cell_text(cell: Any) -> str | None:
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return str(cell.value)
    if cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
        # Only whole numbers long enough to be a NIF or phone are worth looking at.
        value = int(cell.value)
        return str(value) if abs(value) >= 100_000 else None
    return None


def _where(sheet_name: str, r: int, c: int) -> str:
    return f"{sheet_name}!{xlrd.formula.cellname(r, c)}"


def harvest(path: Path) -> tuple[list[Seed], list[Finding], bool]:
    book = xlrd.open_workbook(str(path))
    seeds: list[Seed] = []
    for sheet in book.sheets():
        grid = [[_cell_text(cell) or "" for cell in sheet.row(r)] for r in range(sheet.nrows)]
        seeds += seeds_from_grid(grid)
    return dedupe(seeds), [], False


def texts(path: Path) -> list[tuple[str, str]]:
    book = xlrd.open_workbook(str(path))
    out: list[tuple[str, str]] = []
    for sheet in book.sheets():
        out.append((f"folha {sheet.name}", sheet.name))
        for r in range(sheet.nrows):
            for c in range(sheet.ncols):
                text = _cell_text(sheet.cell(r, c))
                if text and text.strip():
                    out.append((_where(sheet.name, r, c), text))
    return out


def _write_keeping_style(ws: Any, r: int, c: int, value: str | float) -> None:
    row = ws._Worksheet__rows.get(r)
    old = row._Row__cells.get(c) if row is not None else None
    xf = getattr(old, "xf_idx", None)
    ws.write(r, c, value)
    if xf is not None:
        ws._Worksheet__rows[r]._Row__cells[c].xf_idx = xf


def transform_file(
    src: Path, dst: Path, engine: TextAnonymizer, strip_images: bool
) -> list[Finding]:
    book = xlrd.open_workbook(str(src), formatting_info=True)
    out = xl_copy(book)
    findings: list[Finding] = [Finding("formulas_to_values")]
    for index, sheet in enumerate(book.sheets()):
        ws = out.get_sheet(index)
        new_name, reps = engine.anonymize(sheet.name)
        if reps:
            ws.set_name(new_name[:31])
        where_sheet = new_name[:31]
        for r_ in reps:
            findings.append(
                Finding("replaced", f"folha {where_sheet}", r_.kind, 1, r_.original, r_.pseudonym)
            )
        for r in range(sheet.nrows):
            for c in range(sheet.ncols):
                cell = sheet.cell(r, c)
                text = _cell_text(cell)
                if not text:
                    continue
                new, reps = engine.anonymize(text)
                if not reps:
                    continue
                numeric = cell.ctype == xlrd.XL_CELL_NUMBER and new.isdigit()
                _write_keeping_style(ws, r, c, float(new) if numeric else new)
                where = _where(where_sheet, r, c)
                for rep in reps:
                    findings.append(
                        Finding("replaced", where, rep.kind, 1, rep.original, rep.pseudonym)
                    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(dst))
    return findings


def scan_file(path: Path, checker: TextAnonymizer) -> list[Finding]:
    findings: list[Finding] = []
    for where, text in texts(path):
        for r in checker.residuals(text):
            code = "residual" if r.severity == "error" else "possible_name"
            findings.append(Finding(code, where, r.kind, original=r.value))
    for kind in sorted(set(checker.binary_hits(path.read_bytes()))):
        findings.append(Finding("pii_in_binary", "ficheiro", kind))
    return findings
