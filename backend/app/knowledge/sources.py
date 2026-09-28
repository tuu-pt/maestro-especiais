"""Texts of a reference project (data/fixtures/<code>), each with where it was read.

Used to seed the knowledge base. File kinds are found by content (the anonymized fixtures may
have other names); a file present twice (same bytes) is read once. Only data/fixtures is read.
"""

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import docx
import xlrd
from docx.document import Document as DocxDocument

from app.ingest import bom, tabela_calculo
from app.ingest.detect import detect
from app.ingest.pipeline import ReaderError
from app.ingest.written import docx_texts, piece_kind

READ = (".xlsx", ".xlsm", ".xls", ".docx")
SOURCE_OF_KIND = {"calc_summary": "Tabela", "calc_circuit": "09-Folha", "mqt": "MQT", "lpu": "LPU"}


@dataclass(frozen=True)
class SourceText:
    project: str
    source: str  # Tabela, 09-Folha, MQT, LPU, MDJ, CTE, Formulário
    file: str  # path inside the project folder
    locator: str  # cell, line or paragraph
    text: str


def docx_kind(document: DocxDocument) -> str | None:
    """MDJ, CTE or a form (identificação, termo), from the title (the first paragraphs)."""
    kind = piece_kind(document)
    return "Formulário" if kind in ("IDENTIFICACAO", "TERMO") else kind


def unique_files(root: Path) -> Iterator[Path]:
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in READ or path.name.startswith("~$"):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in seen:
            seen.add(digest)
            yield path


def project_texts(fixtures: Path, code: str) -> Iterator[SourceText]:
    root = fixtures / code
    for path in unique_files(root):
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if path.suffix.lower() == ".docx":
            document = docx.Document(str(path))
            kind = docx_kind(document)
            if kind:
                for locator, text in docx_texts(document):
                    yield SourceText(code, kind, rel, locator, text)
            continue
        kind = detect(path.name, data).kind
        source = SOURCE_OF_KIND.get(kind)
        if source is None:
            continue
        try:
            yield from _sheet_texts(code, source, rel, kind, data)
        except ReaderError:
            continue  # unreadable: the ingestion reports it, the seed skips it


def _sheet_texts(code: str, source: str, rel: str, kind: str, data: bytes) -> Iterator[SourceText]:
    if kind == "calc_summary":
        for circuit in tabela_calculo.read(data).circuits:
            if circuit.fields.get("cable_raw"):
                yield SourceText(code, source, rel, circuit.source_ref, circuit.fields["cable_raw"])
    elif kind in ("mqt", "lpu"):
        for line in bom.read(data).lines:
            if line.designation:
                yield SourceText(code, source, rel, line.source_ref, line.designation)
    elif kind == "calc_circuit":
        book = xlrd.open_workbook(file_contents=data)
        for sheet in book.sheets():
            for r in range(sheet.nrows):
                for c in range(sheet.ncols):
                    value = sheet.cell_value(r, c)
                    if isinstance(value, str) and re.search(r"[A-Za-z]", value):
                        cell = f"{xlrd.colname(c)}{r + 1}"
                        yield SourceText(code, source, rel, f"{sheet.name}!{cell}", value)
