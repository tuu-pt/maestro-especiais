"""Facts read from the text of the MDJ and the CTE, without the LLM (Phase 5).

Each extractor reads only the sections of its subject (the key of the section, as in the
Phase 3 split): the power in the supply sections, the chargers in the section on electric
vehicles, the boards in the sections on boards. Outside them nothing is read, so that "um
carregador" of a microphone is not an EV charger. What cannot be read reliably is a fact marked
"não comparável", with the reason.

Identification and technician come from the cover and the signature, by their labels (the same
readers as Phase 3), only in the pieces made by hand: in an assembled piece they are value marks.
"""

import re
from collections.abc import Iterable

from app.ingest import boards as board_names
from app.ingest.detect import fold
from app.ingest.keys import KEYS
from app.knowledge import cables
from app.library.facts import cover_facts, signature_facts
from app.validation.normalize import number, shown_number
from app.validation.pieces import Fact, Paragraph
from app.validation.quantities import TIMES, count

QTY_BOARDS = "qty.quadros"
BOARD_NAMES = "names.quadros"
QTY_EV = "qty.ve_carregadores"
QTY_PV_MODULES = "qty.fv_modulos"
PV_KWP = "fv.potencia_kwp"
CABLE = "cabo"
POWER = "ele.potencia_alimentar_kva"
POWER_EXISTING = "ele.potencia_existente_kva"
NOT_PERSONAL = {"tec.titulo", "doc.local", "doc.data"}

# key of a section contains one of these → the section talks about the subject
BOARD_SECTIONS = ("quadro", "distribuicao")
EV_SECTIONS = ("veiculos_eletricos",)
PV_SECTIONS = ("fotovolt",)

_KVA = re.compile(r"(?<![\w,.])(\d+(?:[.,]\d+)?)\s*kVA\b", re.I)
_KWP = re.compile(r"(?<![\w,.])(\d+(?:[.,]\d+)?)\s*kWp\b", re.I)
_NOT_SUPPLY = re.compile(r"\b(?:ups|gerador|grupo|transformador|inversor|bateria)s?\b\W*$")
_EXISTING = re.compile(r"\b(?:atualmente|actualmente|existente|atual|actual)\b")
_BOARD = re.compile(r"\(?\bQ\.\s?(?:E\.?\s?G|P|[A-Z])[\w.\- ]*?\)?(?=[\s,;:)]|$)")


def personal(key: str) -> bool:
    if key in NOT_PERSONAL:
        return False
    if key.startswith("tec."):
        return True
    info = KEYS.get(key)
    return bool(info and info.personal)


def where(p: Paragraph) -> dict[str, object]:
    return {"section": p.section_key, "section_title": p.section_title, "paragraph": p.index,
            "section_id": p.section_id, "anchor": p.anchor}  # fmt: skip


def _in(p: Paragraph, subjects: tuple[str, ...]) -> bool:
    return p.section_kind == "block" and any(s in p.section_key for s in subjects)


def power(paragraphs: Iterable[Paragraph], piece: str) -> list[Fact]:
    out = []
    for p in paragraphs:
        if p.section_kind != "block":
            continue
        for m in _KVA.finditer(p.text):
            before = fold(p.text[max(0, m.start() - 70) : m.start()])
            if _NOT_SUPPLY.search(before[-30:]):
                continue  # "UPS 10kVA", "gerador de 30 kVA": not the supply
            value = number(m.group(1))
            if value is None:
                continue
            key = POWER_EXISTING if _EXISTING.search(before) else POWER
            context = p.text[max(0, m.start() - 60) : m.end() + 20].strip()
            shown = f"{shown_number(value)} kVA"
            out.append(Fact(key, value, piece, where(p), shown=shown, note=context))
    return out


def boards(paragraphs: Iterable[Paragraph], piece: str) -> list[Fact]:
    out: list[Fact] = []
    names: dict[str, str] = {}
    first: Paragraph | None = None
    for p in paragraphs:
        if not _in(p, BOARD_SECTIONS):
            continue
        if not any(f.key == QTY_BOARDS for f in out):
            q = count(p.text, r"quadros\s+eletricos")
            if q is not None:
                out.append(Fact(QTY_BOARDS, q.value, piece, where(p), shown=str(q.value),
                                note=f"«{q.text}» ({q.how})"))  # fmt: skip
        for m in _BOARD.finditer(p.text):
            name = m.group(0).strip("() ")
            core = board_names.core(name)
            if core and core not in names:
                names[core] = name
                first = first or p
    if names and first is not None:
        out.append(Fact(BOARD_NAMES, sorted(names), piece, where(first),
                        shown=", ".join(names.values()),
                        note="quadros nomeados no texto (não é o número total)"))  # fmt: skip
    return out


def ev_chargers(paragraphs: Iterable[Paragraph], piece: str) -> list[Fact]:
    for p in paragraphs:
        if not _in(p, EV_SECTIONS):
            continue
        q = count(p.text, r"carregador(?:es)?", container=r"(?:pedestal|pedestais|postos?)")
        if q is not None:
            note = f"«{q.text}» ({q.how})"
            if TIMES in q.how:
                note += "; «capacidade» pode querer dizer tomadas e não carregadores instalados"
            return [Fact(QTY_EV, q.value, piece, where(p), shown=str(q.value), note=note)]
    return []


def pv(paragraphs: Iterable[Paragraph], piece: str) -> list[Fact]:
    out: list[Fact] = []
    for p in paragraphs:
        if not _in(p, PV_SECTIONS):
            continue
        if not any(f.key == QTY_PV_MODULES for f in out):
            q = count(p.text, r"modulos?(?:\s+fotovoltaicos?)?")
            if q is not None:
                out.append(Fact(QTY_PV_MODULES, q.value, piece, where(p), shown=str(q.value),
                                note=f"«{q.text}» ({q.how})"))  # fmt: skip
        if not any(f.key == PV_KWP for f in out) and (m := _KWP.search(p.text)):
            value = number(m.group(1))
            if value is not None:
                out.append(Fact(PV_KWP, value, piece, where(p),
                                shown=f"{shown_number(value)} kWp"))  # fmt: skip
    return out


def cable_facts(paragraphs: Iterable[Paragraph], piece: str) -> list[Fact]:
    out = []
    for p in paragraphs:
        if p.section_kind != "block":
            continue
        for d in cables.find(p.text):
            out.append(Fact(CABLE, d.family, piece, where(p), shown=d.raw,
                            note=p.text[:160]))  # fmt: skip
    return out


def identification(paragraphs: list[Paragraph], piece: str) -> list[Fact]:
    """Cover and signature, by their labels (Phase 3 readers)."""
    out = []
    for kind, reader in (("cover", cover_facts), ("signature", signature_facts)):
        lines = [p for p in paragraphs if p.section_kind == kind]
        for fact in reader([p.text for p in lines]):
            wanted = fact.value.lower()
            line = next((p for p in lines if wanted in " ".join(p.text.split()).lower()),
                        lines[0] if lines else None)  # fmt: skip
            value = fact.value
            if fact.key in ("tec.oet", "tec.cc"):
                value = re.sub(r"[^0-9A-Za-z]", "", value)
            out.append(Fact(fact.key, value, piece, where(line) if line else {},
                            personal=personal(fact.key),
                            shown=None if personal(fact.key) else fact.value))  # fmt: skip
    return out


def read(paragraphs: list[Paragraph], piece: str, *, with_identification: bool) -> list[Fact]:
    facts = power(paragraphs, piece) + boards(paragraphs, piece)
    facts += ev_chargers(paragraphs, piece) + pv(paragraphs, piece) + cable_facts(paragraphs, piece)
    if with_identification:
        facts += identification(paragraphs, piece)
    return facts
