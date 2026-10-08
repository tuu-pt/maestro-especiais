"""Reference equipment and requirements read from the text of a CTE section (Phase 7).

A reference line names a manufacturer and a model or a reference, e.g.:
- "Portinhola PBT Tri, referência +32470 da marca Quitérios, ou equivalente."
- "Interruptor unipolar - EFAPEL - SIZA Ref. 45011 S ou equivalente:"
- "Tipo L14 - Aplique …, 1,5W, IP65 IK10, modelo 2525 da Tromilux, ou equivalente."
- "Equipamento de Referência: JSL - Tubo VD FLH ou equivalente"
- "… sendo o modelo de referência de projeto TJAS471 da Hager ou equivalente:"
The other lines are characteristics: of the reference line above them, or of the whole block
when they come before the first one. Every parameter (app.equipment.params) on a line is also a
requirement of the block: of the equipment of its line, or of all its equipment. Nothing here
is final: all is "proposed" for the curator [A CONFIRMAR].
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.equipment import block_category
from app.equipment.params import INFO, PARAMS, Reading, read
from app.ingest.detect import fold

# Manufacturers named in the reference CTEs and other usual ones (the curator adds the rest).
BRANDS = (
    "ABB", "Audio-Technica", "Avitel", "Catchbox", "CENTOLIGHT", "CHAMSYS", "Climar", "EFAPEL",
    "EPSON", "Exporlux", "Global Fire", "Hager", "Hikvision", "Honeywell", "Huawei", "Indelague",
    "INFOCONTROL", "JSL", "Legrand", "MOREK", "Multitubos", "Napofix", "PERRY", "Philips",
    "Quitérios", "Schneider Electric", "Siemens", "SUNFER", "Tromilux", "Trina",
    "Visual Productions",
)  # fmt: skip
_BRANDS = [(b, re.compile(rf"(?<![\w-]){re.escape(fold(b))}(?![\w-])")) for b in BRANDS]
_MARCA = re.compile(r"\bda marca\s+([A-Za-zÀ-ÿ][\w.&-]*)")
_LUMINAIRE = re.compile(
    r"^\s*(?:tipo\s+)?((?:L\d+(?:\.\d+)?|SNC|BS)(?:\s*e\s*L\d+(?:\.\d+)?)*)\s*[-\u2013\u2014]",
    re.I,
)
_QUOTED = r"[\u00b4'\u2018\u2019\"\u201c\u201d]\s*(.+?)\s*[\u00b4'\u2018\u2019\"\u201c\u201d]"
_STOP = r"(?=\s*(?:,|;|:|\s+da\s|\s+de\s|\s+do\s|\s+ou\b|\s+com\b|\s+na cor|\s+equipad|$))"
_MODEL = re.compile(
    rf"\bmodelo(?:\s+de\s+refer[eê]ncia(?:\s+de\s+projeto)?)?\s*:?\s*(?:{_QUOTED}|(.+?){_STOP})",
    re.I,
)
_SERIES = re.compile(rf"\bs[eé]rie\s+(.+?){_STOP}", re.I)
_TYPE = re.compile(rf"\bdo tipo\s+(.+?){_STOP}", re.I)
_REFERENCE = re.compile(
    r"\bref(?:er[eê]ncia|\.ª|ª|\.)?(?![a-zà-ÿ])\s*[:.]?\s*"
    r"([+]?[A-Z0-9][\w.\-/()+]*(?:\s+[A-Z0-9][\w.\-/()+]*)*?)"
    r"(?=\s*(?:,|;|:|\(|\s+ou\b|\s+da\b|\s+centro|\s+com\b|\s+e\s+respetivos|$))",
    re.I,
)
_EQUIVALENT = re.compile(r"\bou\s+(?:de qualidade e caracter[ií]sticas\s+)?equivalentes?\b", re.I)
_NAME_CUT = re.compile(
    r"\s[-\u2013\u2014]\s|,|:|\.\s|\.$|\(|\s(?:dever[aá]|ser(?:á|ão|a|ao)|foi|foram|do tipo|"
    r"da marca|a instalar|a aplicar|selecionad\w*|previst\w*|s[aã]o|é|refer[eê]ncia|modelo|REF|"
    r"Ref|s[eé]rie)(?![\w])",
    re.I,
)


@dataclass
class Found:
    """A reference equipment of a CTE line."""

    name: str
    manufacturer: str
    model: str | None
    reference: str | None
    code: str | None
    or_equivalent: bool
    unit: int  # index of its line in the source section
    text: str
    readings: list[Reading] = field(default_factory=list)  # its line and its characteristics

    @property
    def identity(self) -> str:
        parts = [self.manufacturer, self.reference or "", self.model or "", self.code or "",
                 self.name[:80]]  # fmt: skip
        return "|".join(fold(p).strip() for p in parts)[:300]


@dataclass
class Need:
    """A requirement read from a CTE line: of `owner` (a Found) or of the whole block."""

    param: str
    operator: str
    value: Any
    unit: str
    line: int
    text: str
    owner: Found | None


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"^[\s\-\u2013\u2014:]+|[\s\-\u2013\u2014,;:.]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value or None


def manufacturer(text: str) -> str | None:
    folded = fold(text)
    hits = [(m.start(), b) for b, p in _BRANDS if (m := p.search(folded))]
    if hits:
        return min(hits)[1]
    m = _MARCA.search(text)
    return m.group(1) if m else None


def _after_brand(text: str, brand: str) -> str | None:
    """ "JSL 317N, ou equivalente" -> 317N; "JSL - Tubo VD FLH ou …" -> Tubo VD FLH."""
    m = re.search(rf"(?<![\w-]){re.escape(brand)}(?![\w-])", text, re.I)
    if m is None:
        return None
    rest = text[m.end() :]
    rest = re.sub(r"^\s*(?:S\.?A\.?|Lda\.?)\s*", "", rest)
    rest = re.sub(r"^[\s\-\u2013\u2014]+", "", rest)
    if re.match(r"(?i)ref", rest):
        return None
    cut = re.search(r",|;|:|\s+ou\b|\s+da\b|\s+de\b|\s+e\s|\s+na cor|\s+para\b|\s+com\b|"
                    r"\s+inclinad|\s+ref\b|\s+ref\.|\s+[-\u2013\u2014]\s", rest, re.I)  # fmt: skip
    model = _clean(rest[: cut.start()] if cut else rest)
    if model and not (model[0].isupper() or model[0].isdigit() or model[0] == "+"):
        return None  # "composto por um receptor": a description, not a model
    return model


def _reference(text: str) -> str | None:
    """«Ref. 45011 S», «referência +32470», «REF. KNX TXD505»: only a code with a digit."""
    for m in _REFERENCE.finditer(text):
        value = _clean(re.sub(r"^(?:[a-zà-ÿ]+\s+)+", "", m.group(1)))
        if value and re.search(r"\d", value):
            return value
    return None


def _strip_brand(value: str | None, brand: str) -> str | None:
    if value is None:
        return None
    return _clean(re.sub(rf"^{re.escape(brand)}\s+", "", value, flags=re.I))


def _name(text: str, code: str | None) -> str:
    body = text
    if code:
        body = _LUMINAIRE.sub("", text, count=1)
    body = re.sub(r"^\s*(?:equipamento de refer[eê]ncia|modelo)\s*:\s*", "", body, flags=re.I)
    body = re.sub(r"^\s*(?:os|as|o|a)\s+", "", body, flags=re.I)
    cut = _NAME_CUT.search(body)
    name = (body[: cut.start()] if cut else body).strip()
    name = name[:1].upper() + name[1:]
    return name[:120]


def reference_line(text: str, unit: int, title: str = "") -> Found | None:
    """The equipment a line names, when it names a manufacturer and a model or a reference."""
    brand = manufacturer(text)
    if brand is None:
        return None
    code_m = _LUMINAIRE.match(text)
    code = re.sub(r"(?i)\s*\be\b\s*", "/", code_m.group(1)).upper() if code_m else None
    reference = _reference(text)
    model = None
    if m := _MODEL.search(text):
        model = _strip_brand(m.group(1) or m.group(2), brand)
    if model is None and (m := _SERIES.search(text)):
        model = _clean(m.group(1))
    if model is None and reference is None and (m := _TYPE.search(text)):
        model = _strip_brand(m.group(1), brand)
        if model and fold(model) == fold(brand):
            model = None
    if model is None:
        model = _after_brand(text, brand)
    if not model and not reference:
        return None
    name = _name(text, code)
    if not name or fold(name).startswith((fold(brand), "dever", "considerou", "edificio", "para ")):
        name = title or name or brand
    return Found(name=name, manufacturer=brand, model=model, reference=reference,
                 code=code, or_equivalent=bool(_EQUIVALENT.search(text)), unit=unit,
                 text=text)  # fmt: skip


@dataclass
class SectionReading:
    category: str
    found: list[Found]
    needs: list[Need]


def read_section(block_key: str, lines: list[tuple[int, str]], title: str = ""
                 ) -> SectionReading | None:  # fmt: skip
    """Equipment and requirements of one CTE section: (index of the unit, text) per line."""
    category = block_category(block_key)
    if category is None:
        return None
    found: list[Found] = []
    needs: list[Need] = []
    owner: Found | None = None
    for index, text in lines:
        if not text.strip():
            continue
        item = reference_line(text, index, title)
        if item is not None:
            found.append(item)
            owner = item
        readings = list(read(text))
        if item is not None:
            item.readings += readings
        elif owner is not None:
            owner.readings += readings  # a characteristic of the equipment above
        for r in readings:
            if PARAMS[r.name].operator == INFO:
                continue
            needs.append(Need(r.name, PARAMS[r.name].operator, r.value, r.unit, index, text,
                              owner))  # fmt: skip
    return SectionReading(category, found, needs)


def category_of(found: Found, block: str) -> str:
    """The block's category, except a box named in the supply block (caixa para contador)."""
    if block == "portinhola" and "caixa" in fold(found.name):
        return "caixa"
    return block
