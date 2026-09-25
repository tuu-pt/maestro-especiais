"""Reader of the PDF of the drawings (peças desenhadas): only three things (SPEC 8.2, Phase 2).

1. The index sheet: code (EL001 or 001), title, date and revision of every sheet.
2. The title block (carimbadura) of every page: requerente, project, specialty, phase, date,
   project code, and the sheet's own title and code. It repeats on every page: pages that
   disagree give one candidate per value, and the ficha opens a FichaConflict.
3. The number of pages.

Text comes from pypdfium2 as positioned runs (decision of 24 Sep 2026: pdfplumber took ~12 s a
page on R2). Pages may be rotated; runs are put in display coordinates. Mirrored text (plans
seen from below, "ONROF") and runs drawn twice are dropped. The legend (sockets, luminaires
L1…) is read in a later phase. Nothing is computed; the index/pages comparison is DES-01's
(Phase 5), the ficha only shows it (case C4).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.ingest.base import Candidate, ReadResult
from app.ingest.detect import fold
from app.ingest.pipeline import ReaderError

TITLE_BLOCK_X = 0.78  # the title block is the right strip of the sheet, as displayed
LABELS = {
    "requerente": "requerente",
    "projeto": "projeto",
    "especialidade": "especialidade",
    "designacao": "designacao",
    "observacoes": "observacoes",
    "nome ficheiro": "ficheiro",
    "codigo": "codigo",
    "equipa": "equipa",
}
_SHEET_CODE = re.compile(r"^(?:EL)?\d{3}$")
_INDEX_ROW = re.compile(
    r"^(?P<code>(?:EL)?\d{3})\s+(?P<title>.+?)\s+(?P<date>\d{2}/\d{2})(?:\s+(?P<rev>\S{1,3}))?$"
)
_MONTH_YEAR = re.compile(
    r"^(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|"
    r"dezembro)\s+\d{4}$"
)
_SCALE = re.compile(r"^(s/\s*escala|\d+:\d+)$")
_REPEATED = re.compile(r"^(.{2,}?)(?:\s?\1)+$")  # "ABCABC": drawn twice
_ADDRESS = re.compile(r"^(rua|av\.?|avenida|travessa|largo|estrada|praca|lugar)\b|\d{4}-\d{3}")


@dataclass(frozen=True)
class Run:
    y: float
    x: float
    text: str
    x1: float = 0.0  # right edge, as displayed


@dataclass
class Page:
    number: int
    width: float
    runs: list[Run]


@dataclass
class DrawingsReading:
    pages: int
    index: list[dict[str, str | None]]
    sheets: list[dict[str, Any]]  # per page: code and title of the sheet
    result: ReadResult
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- text runs


def _mirrored(textpage: Any, first: int, count: int) -> bool:
    """Most characters drawn with a negative determinant: a mirrored text."""
    matrix = pdfium_c.FS_MATRIX()
    flipped = seen = 0
    for i in range(first, first + count):
        if pdfium_c.FPDFText_GetMatrix(textpage.raw, i, matrix):
            seen += 1
            flipped += (matrix.a * matrix.d - matrix.b * matrix.c) < 0
    return seen > 0 and flipped * 2 > seen


def _display(
    rotation: int, width: float, height: float, box: tuple[float, ...]
) -> tuple[float, float, float]:
    """Left, top and right of a box on the page as displayed (x to the right, y down)."""
    left, bottom, right, top = box
    if rotation == 90:
        return bottom, left, top
    if rotation == 180:
        return width - right, bottom, width - left
    if rotation == 270:
        return width - top, height - right, width - bottom
    return left, height - top, right


def page_runs(page: Any) -> list[Run]:
    textpage = page.get_textpage()
    width, height = page.get_size()
    rotation = page.get_rotation()
    runs: dict[tuple[int, int, str], Run] = {}
    for i in range(textpage.count_rects()):
        box = textpage.get_rect(i)
        text = " ".join(textpage.get_text_bounded(*box).split())
        if not text:
            continue
        repeated = _REPEATED.match(text)
        if repeated:
            text = repeated.group(1)
        first = textpage.get_index(box[0] + 0.5, (box[1] + box[3]) / 2, 2, 2)
        if first is not None and first >= 0 and _mirrored(textpage, first, len(text)):
            continue
        x, y, x1 = _display(rotation, width, height, box)
        runs.setdefault((round(y), round(x), text), Run(y, x, text, x1))  # drawn twice: once
    return sorted(runs.values(), key=lambda r: (r.y, r.x))


def _lines(
    runs: Iterable[Run], tolerance: float = 3.5, gap: float | None = None
) -> list[tuple[float, float, str]]:
    """Runs on the same baseline joined into lines: (y, x, text).

    With a gap, runs further apart than it on the same baseline are separate lines (a title
    block next to text of the plan).
    """
    rows: list[list[Run]] = []
    for run in sorted(runs, key=lambda r: (r.y, r.x)):
        if rows and abs(rows[-1][0].y - run.y) <= tolerance:
            rows[-1].append(run)
        else:
            rows.append([run])
    out = []
    for row in rows:
        row.sort(key=lambda r: r.x)
        pieces = [[row[0]]]
        for run in row[1:]:
            previous = pieces[-1][-1]
            if gap is not None and run.x - max(previous.x1, previous.x) > gap:
                pieces.append([run])
            else:
                pieces[-1].append(run)
        out += [(p[0].y, p[0].x, " ".join(r.text for r in p)) for p in pieces]
    return out


# ---------------------------------------------------------------- title block and index


def title_block(page: Page) -> dict[str, str]:
    """Fields of the title block: each value is between its label and the next label."""
    strip = [r for r in page.runs if r.x >= page.width * TITLE_BLOCK_X]
    found: dict[str, Run] = {}
    for run in strip:  # the first of each: "código" also appears in the copyright note
        name = LABELS.get(fold(run.text))
        if name and name not in found:
            found[name] = run
    if not found:
        return {}
    column = min(r.x for r in found.values())  # labels and values are aligned on it
    labels = sorted((r.y, name) for name, r in found.items())
    fields: dict[str, str] = {}
    for n, (y, name) in enumerate(labels):
        end = labels[n + 1][0] if n + 1 < len(labels) else float("inf")
        inside = [r for r in strip if y + 1 < r.y < end - 1 and fold(r.text) not in LABELS]
        # Text lines only if they start on the column: text of the plan can run under the title
        # block. Dates, scales and sheet codes are recognized by their form wherever they are.
        all_lines = _lines(inside, gap=18)
        lines = [t for _, x, t in all_lines if abs(x - column) <= 6]
        if name == "requerente":
            fields["requerente"] = " ".join(lines)
        elif name == "projeto":
            name_lines = []
            for line in lines:
                if _ADDRESS.search(fold(line)):
                    break
                name_lines.append(line)
            fields["projeto"] = " ".join(name_lines)
        elif name == "especialidade":
            if lines:
                fields["especialidade"] = lines[0]
            if len(lines) > 1:
                fields["fase"] = lines[1]
        elif name == "designacao":
            title: list[str] = []
            aligned = set(lines)
            for line in (t for _, _, t in all_lines):
                folded = fold(line)
                if _MONTH_YEAR.match(folded):
                    fields["data"] = line
                elif _SCALE.match(folded):
                    fields["escala"] = line
                elif _SHEET_CODE.match(line.replace(" ", "")):
                    fields["folha"] = line.replace(" ", "")
                elif "data" not in fields and line != "-" and line in aligned:
                    title.append(line)
            fields["titulo"] = " ".join(title)
        elif name == "codigo" and lines:
            fields["codigo"] = lines[0]
    return {k: v for k, v in fields.items() if v}


def index_rows(page: Page) -> list[dict[str, str | None]]:
    """Rows of the index table, outside the title block."""
    body = [r for r in page.runs if r.x < page.width * TITLE_BLOCK_X]
    rows = []
    for _, _, text in _lines(body):
        match = _INDEX_ROW.match(text)
        if match:
            rev = match.group("rev")
            rows.append(
                {
                    "codigo": match.group("code"),
                    "titulo": match.group("title").strip(),
                    "data": match.group("date"),
                    "revisao": None if rev in (None, "-") else rev,
                }
            )
    unique: dict[str, dict[str, str | None]] = {}
    for row in rows:  # a code listed twice (text drawn twice) counts once
        unique.setdefault(str(row["codigo"]), row)
    return list(unique.values())


# ---------------------------------------------------------------- reading


def open_pdf(data: bytes) -> Any:
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise ReaderError("PDF ilegível ou corrompido.") from exc


def is_drawings(data: bytes) -> bool:
    """A drawings set has a title block (Especialidade + Designação) on its first page."""
    document = open_pdf(data)
    try:
        if len(document) == 0:
            return False
        page = document[0]
        labels = {fold(r.text) for r in page_runs(page)}
        return {"especialidade", "designacao"} <= labels
    finally:
        document.close()


FIELD_KEYS = {
    "requerente": "id.requerente.nome",
    "projeto": "id.obra.designacao",
    "especialidade": "pd.carimbadura.especialidade",
    "fase": "pd.carimbadura.fase",
    "data": "pd.carimbadura.data",
    "codigo": "pd.carimbadura.codigo",
}


def _pages_label(numbers: list[int]) -> str:
    if len(numbers) == 1:
        return f"pág. {numbers[0]}"
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"págs. {numbers[0]}-{numbers[-1]}"
    return "págs. " + ", ".join(str(n) for n in numbers[:6]) + ("…" if len(numbers) > 6 else "")


def read(data: bytes) -> DrawingsReading:
    document = open_pdf(data)
    try:
        pages = [
            Page(number=i + 1, width=document[i].get_size()[0], runs=page_runs(document[i]))
            for i in range(len(document))
        ]
    finally:
        document.close()
    result = ReadResult(source_type="drawing")
    reading = DrawingsReading(pages=len(pages), index=[], sheets=[], result=result)
    blocks = [(p.number, title_block(p)) for p in pages]
    for page in pages:
        rows = index_rows(page)
        if len(rows) >= 2:
            reading.index = rows
            index_page = page.number
            break
    else:
        index_page = None
        reading.warnings.append("O PDF não tem folha de índice (EL001…): índice não lido.")
    if not any(block for _, block in blocks):
        reading.warnings.append(
            "Carimbadura não encontrada: o PDF não parece ser das peças desenhadas."
        )
    # One candidate per distinct value of each field, with the pages it appears on.
    for name, key in FIELD_KEYS.items():
        by_value: dict[str, list[int]] = {}
        for number, block in blocks:
            if block.get(name):
                by_value.setdefault(block[name], []).append(number)
        for value, numbers in by_value.items():
            result.values.append(
                Candidate(key, value, f"PDF · {_pages_label(numbers)} · carimbadura")
            )
    reading.sheets = [
        {"pagina": n, "codigo": b.get("folha"), "titulo": b.get("titulo")} for n, b in blocks
    ]
    if reading.index:
        ref = f"PDF · pág. {index_page} · índice"
        result.values.append(Candidate("pd.indice", reading.index, ref))
    result.values.append(Candidate("pd.n_paginas_pdf", len(pages), "PDF · número de páginas"))
    result.values.append(Candidate("pd.folhas", reading.sheets, "PDF · carimbadura de cada página"))
    return reading


def _digits(code: object) -> str:
    return "".join(c for c in str(code or "") if c.isdigit())


def index_check(
    index: list[dict[str, Any]], sheets: list[dict[str, Any]], pages: int
) -> dict[str, Any]:
    """What the ficha shows about the index and the PDF (case C4); DES-01 is Phase 5.

    Sheets are compared by the digits of their code (EL001 and 001 are the same sheet). The
    index sheet itself need not be listed. Nothing is computed beyond this comparison.
    """
    listed = {_digits(r.get("codigo")): r.get("codigo") for r in index if _digits(r.get("codigo"))}
    drawn = {_digits(s.get("codigo")): s for s in sheets if _digits(s.get("codigo"))}
    missing = [listed[k] for k in sorted(listed) if k not in drawn]
    unlisted = [
        drawn[k].get("codigo")
        for k in sorted(drawn)
        if k not in listed and fold(drawn[k].get("titulo") or "") != "indice"
    ]
    return {
        "index_sheets": len(index),
        "pages": pages,
        "missing_in_pdf": missing,
        "not_in_index": unlisted,
        "matches": not missing and not unlisted,
    }


def page_runs_from(data: bytes, page: int = 0) -> list[Run]:
    """The text runs of one page (for tests and diagnostics)."""
    document = open_pdf(data)
    try:
        return page_runs(document[page])
    finally:
        document.close()
