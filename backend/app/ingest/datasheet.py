"""Datasheets of the manufacturers (PDF), read without the LLM (Phase 7).

The text of each page (pypdfium2) goes through the patterns of app.equipment.params: every
parameter found, with its page, is "extracted" until a curator reviews it. The issue date is
read only next to a word that dates the document (Rev., revisão, edição, data, date, version,
fecha…), as a day, a month or a month name; otherwise the curator writes it. The language is the
one with the most of its frequent words (pt, en, es). Datasheets are public documents of the
manufacturers: nothing of a person is read here.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from app.equipment.params import Reading, read
from app.ingest.detect import fold
from app.ingest.pipeline import ReaderError

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "enero": 1, "febrero": 2, "mayo": 5, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_DATING = (
    r"(?:rev(?:\.|isao|ision)?|edicao|edition|data|date|version|versao|fecha|actualizad[oa]"
    r"|updated|issued?)"
)
_DATE = (
    r"(?P<d>\d{4}-\d{2}(?:-\d{2})?"  # 2021-03 or 2021-03-15
    r"|\d{1,2}[/.]\d{1,2}[/.]\d{4}"  # 15/03/2021
    r"|\d{1,2}[/.]\d{4}"  # 03/2021
    rf"|(?:{'|'.join(sorted(MONTHS, key=len, reverse=True))})\.?\s*(?:de\s+)?\d{{4}})"
)
_ISSUE = re.compile(rf"\b{_DATING}(?![a-z])\W{{0,12}}(?:[a-z.]{{1,6}}\W{{1,4}})?{_DATE}")
LANGUAGE_WORDS = {
    "pt": {"de", "para", "com", "nao", "protecao", "potencia", "tensao", "dimensoes", "e", "em"},
    "en": {"the", "and", "with", "for", "power", "voltage", "dimensions", "of", "to", "in"},
    "es": {"el", "la", "con", "para", "potencia", "tension", "dimensiones", "y", "en", "los"},
}


@dataclass
class Found:
    reading: Reading
    page: int  # 1-based


@dataclass
class DatasheetReading:
    pages: int
    params: list[Found] = field(default_factory=list)
    issue_date: date | None = None
    issue_date_text: str | None = None
    language: str | None = None
    warnings: list[str] = field(default_factory=list)


def page_texts(data: bytes) -> list[str]:
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise ReaderError("PDF ilegível ou corrompido.") from exc
    try:
        return [document[i].get_textpage().get_text_range() for i in range(len(document))]
    finally:
        document.close()


def issue_date(text: str) -> tuple[date | None, str | None]:
    """(date, the text it was read from) of the first dated mention."""
    for m in _ISSUE.finditer(fold(text)):
        raw = m.group("d")
        when = _to_date(raw)
        if when is not None:
            return when, m.group(0).strip()[:60]
    return None, None


def _to_date(raw: str) -> date | None:
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", raw):
            return date(int(m[1]), int(m[2]), int(m[3] or 1))
        if m := re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", raw):
            return date(int(m[3]), int(m[2]), int(m[1]))
        if m := re.fullmatch(r"(\d{1,2})[/.](\d{4})", raw):
            return date(int(m[2]), int(m[1]), 1)
        if m := re.fullmatch(r"([a-z_]+)\.?\s*(?:de\s+)?(\d{4})", raw):
            month = MONTHS.get(m[1])
            return date(int(m[2]), month, 1) if month else None
    except ValueError:
        return None
    return None


def language(text: str) -> str | None:
    words = re.findall(r"[a-z]+", fold(text))
    counts = {lang: sum(1 for w in words if w in vocab) for lang, vocab in LANGUAGE_WORDS.items()}
    best = max(counts, key=lambda k: counts[k])
    return best if counts[best] >= 3 else None


def read_datasheet(data: bytes) -> DatasheetReading:
    texts = page_texts(data)
    out = DatasheetReading(pages=len(texts))
    seen: set[tuple[str, str]] = set()
    for n, text in enumerate(texts, start=1):
        for r in read(text):
            key = (r.name, str(r.value))
            if key not in seen:
                seen.add(key)
                out.params.append(Found(r, n))
        if out.issue_date is None:
            out.issue_date, out.issue_date_text = issue_date(text)
    out.language = language(" ".join(texts))
    if not "".join(texts).strip():
        out.warnings.append("PDF sem texto (digitalizado?): os parâmetros escrevem-se à mão.")
    elif not out.params:
        out.warnings.append("Nenhum parâmetro reconhecido: escrever à mão os que o CTE exige.")
    if out.issue_date is None:
        out.warnings.append("Data de emissão não encontrada: escrever à mão (EQP-02).")
    return out
