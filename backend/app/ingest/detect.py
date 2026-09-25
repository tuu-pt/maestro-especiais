"""What kind of project file is this? Decided from the content, never from the name alone."""

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass

import openpyxl
import xlrd

# Kinds with a reader in Phase 1. The others are stored and read in Phase 2.
READABLE_KINDS = ("ficha_eletrotecnica", "calc_summary", "calc_circuit")

FE_VERSION_CELL = "R45"
_CALC_SHEETS = {"ib", "condutores", "tensao", "proteccao"}
_HEADER_ROWS = 40


@dataclass(frozen=True)
class Detection:
    kind: str
    template_version: str | None = None
    note: str | None = None  # for people; never contains values from the file


def fold(text: object) -> str:
    """Lower case, no accents, single spaces."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return re.sub(r"\s+", " ", plain).strip()


def _row_words(rows: list[list[str]]) -> list[set[str]]:
    return [{fold(c) for c in row if str(c).strip()} for row in rows]


def looks_like_calc_table(rows: list[list[str]]) -> bool:
    return any({"origem", "destino"} <= words for words in _row_words(rows))


def _quantities_kind(rows: list[list[str]]) -> str | None:
    for words in _row_words(rows):
        text = " ".join(words)
        has_designation = "designacao" in text
        has_quantity = any(w.startswith("quant") for w in words)
        if has_designation and has_quantity:
            return "lpu" if "preco" in text else "mqt"
    return None


def _detect_workbook(data: bytes) -> Detection:
    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = [
                ["" if v is None else str(v) for v in row]
                for row in sheet.iter_rows(max_row=_HEADER_ROWS, values_only=True)
            ]
            version = _fe_version(sheet)
            if version:
                return Detection("ficha_eletrotecnica", template_version=version)
            if looks_like_calc_table(rows):
                return Detection("calc_summary")
            kind = _quantities_kind(rows)
            if kind:
                return Detection(kind)
    finally:
        workbook.close()
    return Detection("other", note="Folha de cálculo sem estrutura conhecida.")


def _fe_version(sheet: object) -> str | None:
    try:
        value = sheet[FE_VERSION_CELL].value  # type: ignore[index]
    except (IndexError, KeyError, AttributeError):
        return None
    text = str(value or "").strip()
    return text if text.startswith("FE_v") else None


def _detect_xls(data: bytes) -> Detection:
    book = xlrd.open_workbook(file_contents=data, on_demand=True)
    try:
        names = {fold(n) for n in book.sheet_names()}
    finally:
        book.release_resources()
    if names >= _CALC_SHEETS:
        return Detection("calc_circuit")
    return Detection("other", note="Folha de cálculo antiga sem estrutura conhecida.")


def detect(filename: str, data: bytes) -> Detection:
    """Detect the file kind. Corrupted or unknown files are 'other' with a note, never an error."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if suffix in {"xlsx", "xlsm", "xltx"}:
            return _detect_workbook(data)
        if suffix == "xls":
            return _detect_xls(data)
    except (zipfile.BadZipFile, xlrd.XLRDError, OSError, ValueError, KeyError):
        return Detection("other", note="Ficheiro ilegível ou corrompido.")
    if suffix == "pdf":
        if data[:5] == b"%PDF-":
            return Detection("drawing_pdf")
        return Detection("other", note="PDF ilegível ou corrompido.")
    if suffix == "dwg":
        return Detection("drawing_dwg")
    return Detection("other")
