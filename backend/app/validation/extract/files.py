"""Pieces read from the project files: ficha eletrotécnica, Tabela de Cálculo, MQT/LPU, drawings,
identification and term (Phase 5).

Each file is read again with the reader of its kind (Phases 1 and 2): the validation compares
what each piece says, not the ficha-base the readings were merged into. Only the latest file of
each kind is a piece. Personal values stay in the backend (Fact.personal).
"""

import io
import re
from decimal import Decimal
from typing import Any

import docx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.forms.fill import DOCX_FIELDS, labelled_pairs, section_of
from app.ingest import boards as board_names
from app.ingest import bom, drawings, ficha_eletrotecnica, tabela_calculo
from app.ingest.base import Candidate
from app.ingest.detect import fold
from app.knowledge import cables
from app.models import FichaRevision, Project, ProjectFile
from app.validation.extract import EXTRACTOR_VERSION, Sources, digest, extractor
from app.validation.extract.documents import file_date
from app.validation.extract.text import (
    BOARD_NAMES,
    CABLE,
    LUMINAIRE_CODE,
    QTY_BOARDS,
    QTY_EV,
    QTY_PV_MODULES,
    luminaire_codes,
    luminaire_fact,
    personal,
)
from app.validation.normalize import shown_number
from app.validation.pieces import Fact, Piece, PieceData

KIND_OF_FILE = {
    "ficha_eletrotecnica": "FICHA_ELE",
    "calc_summary": "CALC",
    "mqt": "MQT",
    "lpu": "LPU",
    "drawing_pdf": "DRAWINGS",
    "identificacao_docx": "IDENTIFICACAO",
    "termo_docx": "TERMO",
}
_EV_DESTINATION = re.compile(
    r"^\s*(?:c\.?\s?v\.?\s?e\b|carregador|posto de carregamento|ve\b)", re.I
)
_EV_ARTICLE = re.compile(r"\bcarregador")
_NOT_EV_ARTICLE = re.compile(
    r"^\s*(?:fornecimento e (?:instalacao|montagem) de\s+)?"
    r"(?:pedestal|suporte|coluna|base|cabo|tomada|sinaletica)"
)
_PV_ARTICLE = re.compile(r"\bmodulos? fotovolt")
# "L1" (R1, under «aparelhos de iluminação»), "L8 / L7", "L1 - Luminária …", "SNC - Luminária" (R2)
_LUMINAIRE_ARTICLE = re.compile(
    rf"^\s*({LUMINAIRE_CODE}(?:\s*/\s*{LUMINAIRE_CODE})*)\s*(?:$|[-\u2013\u2014]\s*lumin)", re.I
)


def pieces(db: Session, project: Project, revision: FichaRevision) -> list[Piece | None]:
    latest: dict[str, ProjectFile] = {}
    for f in db.scalars(select(ProjectFile).where(
        ProjectFile.project_id == project.id, ProjectFile.ingest_status == "done",
        ProjectFile.kind.in_(KIND_OF_FILE),
    ).order_by(ProjectFile.created_at)):  # fmt: skip
        latest[f.kind] = f
    out: list[Piece | None] = []
    for f in latest.values():
        out.append(Piece(ref=f"file:{f.id}", kind=KIND_OF_FILE[f.kind], origin="file",
                         content_hash=digest(EXTRACTOR_VERSION, f.checksum), date=file_date(f),
                         file_id=str(f.id)))  # fmt: skip
    return out


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    return value


def _shown(key: str, value: Any) -> str | None:
    if personal(key):
        return None
    if isinstance(value, float | int) and not isinstance(value, bool):
        return shown_number(float(value))
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return ", ".join(value)
    return None if isinstance(value, list | dict) else str(value)


def candidate_facts(values: list[Candidate], piece: str) -> list[Fact]:
    out = []
    for c in values:
        value = _json(c.value)
        out.append(Fact(c.key, value, piece, {"cell": c.source_ref}, personal=personal(c.key),
                        shown=_shown(c.key, value)))  # fmt: skip
        if c.key == "ele.quadros" and isinstance(value, list):
            out += board_facts(value, piece, c.source_ref)
    return out


def board_facts(names: list[str], piece: str, ref: str) -> list[Fact]:
    cores = sorted({board_names.core(n) for n in names if board_names.core(n)})
    return [
        Fact(QTY_BOARDS, len(cores), piece, {"cell": ref}, shown=str(len(cores)),
             note="quadros distintos: " + ", ".join(names)),
        Fact(BOARD_NAMES, cores, piece, {"cell": ref}, shown=", ".join(names)),
    ]  # fmt: skip


def _file(sources: Sources, piece: Piece) -> tuple[ProjectFile, bytes] | None:
    file = sources.db.get(ProjectFile, piece.file_id)
    if file is None or sources.store is None:
        return None
    return file, sources.store.get(file.storage_key)


def _unavailable() -> PieceData:
    return PieceData(warnings=["Ficheiro indisponível: a peça não foi lida."])


@extractor("file:FICHA_ELE")
def read_ficha(sources: Sources, piece: Piece) -> PieceData:
    got = _file(sources, piece)
    if got is None:
        return _unavailable()
    result = ficha_eletrotecnica.read(got[1])
    return PieceData(facts=candidate_facts(result.values, piece.ref), warnings=result.warnings)


@extractor("file:CALC")
def read_calc(sources: Sources, piece: Piece) -> PieceData:
    got = _file(sources, piece)
    if got is None:
        return _unavailable()
    result = tabela_calculo.read(got[1])
    facts = candidate_facts([c for c in result.values if c.key != "ele.cabos"], piece.ref)
    chargers = [c for c in result.circuits
                if _EV_DESTINATION.search(str(c.fields.get("destination") or ""))]  # fmt: skip
    if chargers:
        facts.append(Fact(QTY_EV, len(chargers), piece.ref,
                          {"cell": ", ".join(c.source_ref for c in chargers)},
                          shown=str(len(chargers)),
                          note="troços com destino a carregadores: " + ", ".join(
                              str(c.fields.get("destination")) for c in chargers)))  # fmt: skip
    for c in result.circuits:
        for d in cables.find(str(c.fields.get("cable_raw") or "")):
            where = f"{c.fields.get('origin')} → {c.fields.get('destination')}"
            facts.append(Fact(CABLE, d.family, piece.ref, {"cell": c.source_ref},
                              shown=d.raw, note=where))  # fmt: skip
    return PieceData(facts=facts, warnings=result.warnings)


def _sum(lines: list[bom.BomLine], wanted: re.Pattern[str],
         unwanted: re.Pattern[str] | None = None) -> tuple[float, list[bom.BomLine]]:  # fmt: skip
    found = [line for line in lines if line.kind == "article" and line.designation
             and wanted.search(fold(line.designation))
             and not (unwanted and unwanted.search(fold(line.designation)))
             and line.quantity is not None]  # fmt: skip
    return float(sum(line.quantity or 0 for line in found)), found


@extractor("file:MQT")
@extractor("file:LPU")
def read_bom(sources: Sources, piece: Piece) -> PieceData:
    got = _file(sources, piece)
    if got is None:
        return _unavailable()
    reading = bom.read(got[1])
    facts = candidate_facts(reading.result.values, piece.ref)
    for key, wanted, unwanted in ((QTY_EV, _EV_ARTICLE, _NOT_EV_ARTICLE),
                                  (QTY_PV_MODULES, _PV_ARTICLE, None)):  # fmt: skip
        total, lines = _sum(reading.lines, wanted, unwanted)
        if lines:
            facts.append(Fact(key, total, piece.ref,
                              {"cell": ", ".join(line.source_ref for line in lines)},
                              shown=shown_number(total),
                              note="; ".join(f"{line.code or ''} {line.quantity} {line.unit or ''}"
                                             for line in lines)))  # fmt: skip
    lit = [(line, m) for line in reading.lines if line.kind == "article" and line.designation
           and (m := _LUMINAIRE_ARTICLE.match(line.designation))]  # fmt: skip
    if lit:
        facts.append(luminaire_fact(
            [c for _, m in lit for c in luminaire_codes(m.group(1))], piece.ref,
            {"cell": ", ".join(line.source_ref for line, _ in lit)},
            "; ".join(f"{line.code or ''} {line.quantity} {line.unit or ''}".strip()
                      for line, _ in lit),
        ))  # fmt: skip
    for line in reading.lines:
        if line.kind == "article" and line.designation:
            for d in cables.find(line.designation):
                facts.append(Fact(CABLE, d.family, piece.ref, {"cell": line.source_ref},
                                  shown=d.raw, note=line.designation[:160]))  # fmt: skip
    return PieceData(facts=facts, warnings=reading.warnings)


@extractor("file:DRAWINGS")
def read_drawings(sources: Sources, piece: Piece) -> PieceData:
    got = _file(sources, piece)
    if got is None:
        return _unavailable()
    reading = drawings.read(got[1])
    return PieceData(facts=candidate_facts(reading.result.values, piece.ref),
                     warnings=reading.warnings)  # fmt: skip


@extractor("file:IDENTIFICACAO")
@extractor("file:TERMO")
def read_form(sources: Sources, piece: Piece) -> PieceData:
    """The DGEG forms by their labels, as Phase 4 fills them (app/forms/fill.py)."""
    got = _file(sources, piece)
    if got is None:
        return _unavailable()
    fields = DOCX_FIELDS["identificacao" if piece.kind == "IDENTIFICACAO" else "termo"]
    document = docx.Document(io.BytesIO(got[1]))
    facts = []
    for table in document.tables:
        section = section_of(table)
        for name, _, cell in labelled_pairs(table):
            key = fields.get(section, {}).get(name)
            text = " ".join(cell.text.split())
            if key is None or not text:
                continue
            value: Any = text
            if key in ("tec.oet", "tec.cc"):
                value = re.sub(r"[^0-9A-Za-z]", "", text)
            facts.append(Fact(key, value, piece.ref, {"cell": f"{section}. {name}"},
                              personal=personal(key), shown=_shown(key, value)))  # fmt: skip
    return PieceData(facts=facts)
