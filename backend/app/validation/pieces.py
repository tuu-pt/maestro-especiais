"""The pieces of a project and what is read from them (Phase 5).

A piece is anything the validation compares with the ficha-base: the MDJ and the CTE (assembled
by the tool or made by hand and uploaded), the identification and the term, the ficha
eletrotécnica, the Tabela de Cálculo, the MQT/LPU and the drawings. Each one gives facts
(normalised values with their origin), paragraphs (for the text rules) and sections.

Personal values stay in the backend: a fact knows it is personal and every evidence built from
it is masked (MASK).
"""

from dataclasses import asdict, dataclass, field
from typing import Any

MASK = "•••"

# Columns of the coherence matrix (SPEC 10.E), in the order of the screen
COLUMNS = {
    "MDJ": "MDJ",
    "CTE": "CTE",
    "MQT_LPU": "MQT/LPU",
    "FICHA_ELE": "Ficha ELE",
    "IDENT_TERMO": "Identificação/Termo",
    "CALC": "Tabela de Cálculo",
    "DRAWINGS": "Desenhos",
}

# Piece kind -> (matrix column, label in the messages: "erro provável <label>")
KINDS = {
    "MDJ": ("MDJ", "na MDJ"),
    "CTE": ("CTE", "no CTE"),
    "IDENTIFICACAO": ("IDENT_TERMO", "na identificação"),
    "TERMO": ("IDENT_TERMO", "no termo"),
    "FICHA_ELE": ("FICHA_ELE", "na ficha eletrotécnica"),
    "CALC": ("CALC", "na Tabela de Cálculo"),
    "MQT": ("MQT_LPU", "no MQT"),
    "LPU": ("MQT_LPU", "na LPU"),
    "DRAWINGS": ("DRAWINGS", "nas peças desenhadas"),
}
NAMES = {
    "MDJ": "MDJ",
    "CTE": "CTE",
    "IDENTIFICACAO": "Identificação",
    "TERMO": "Termo",
    "FICHA_ELE": "Ficha eletrotécnica",
    "CALC": "Tabela de Cálculo",
    "MQT": "MQT",
    "LPU": "LPU",
    "DRAWINGS": "Peças desenhadas",
}


@dataclass
class Piece:
    ref: str  # doc:<uuid> or file:<uuid>
    kind: str  # a key of KINDS
    origin: str  # assembled | existing | file
    content_hash: str
    date: str | None = None  # ISO date of the piece (file date, or last edit)
    document_id: str | None = None
    file_id: str | None = None

    @property
    def column(self) -> str:
        return KINDS[self.kind][0]

    @property
    def name(self) -> str:
        suffix = " (existente)" if self.origin == "existing" else ""
        return NAMES[self.kind] + suffix

    @property
    def in_label(self) -> str:
        return KINDS[self.kind][1]

    def as_json(self) -> dict[str, Any]:
        return {**asdict(self), "column": self.column, "name": self.name}


@dataclass
class Fact:
    key: str  # a ficha key (SPEC 7.2) or a validation key (e.g. qty.ve_carregadores)
    value: Any  # normalised: number, text folded for comparison, list…
    piece: str  # Piece.ref
    locator: dict[str, Any] = field(default_factory=dict)  # section, paragraph, cell, page
    personal: bool = False
    comparable: bool = True  # False: read, but not reliably ("não comparável")
    note: str | None = None  # why it is not comparable, or how it was read
    shown: str | None = None  # how the piece writes it (masked when personal)

    def display(self) -> str:
        if self.personal:
            return MASK
        return self.shown if self.shown is not None else str(self.value)


@dataclass
class Paragraph:
    piece: str
    section_key: str
    section_title: str
    section_kind: str  # cover | index | block | signature
    index: int  # position in the section
    text: str  # as the reader sees it (personal values masked in assembled pieces)
    source_text: str | None = None  # assembled pieces: values back as {{v:key}}
    generated: bool = False  # text of the agent
    anchor: str | None = None
    section_id: str | None = None


@dataclass
class SectionInfo:
    piece: str
    key: str  # without the document prefix, e.g. "canalizacoes.canalizacoes_enterradas"
    title: str
    kind: str
    level: int
    active: bool = True
    section_id: str | None = None


@dataclass
class PieceData:
    facts: list[Fact] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    sections: list[SectionInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "facts": [asdict(f) for f in self.facts],
            "paragraphs": [asdict(p) for p in self.paragraphs],
            "sections": [asdict(s) for s in self.sections],
            "warnings": self.warnings,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PieceData":
        return cls(
            [Fact(**f) for f in data.get("facts", [])],
            [Paragraph(**p) for p in data.get("paragraphs", [])],
            [SectionInfo(**s) for s in data.get("sections", [])],
            list(data.get("warnings", [])),
        )
