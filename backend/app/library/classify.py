"""Proposed blocks from the reference MDJ/CTE, paragraph by paragraph (SPEC 8.3, Phase 3).

For each section (same key in both projects), the body elements are aligned (difflib) after each
project's known values were replaced by {{v:<key>}}:

- equal in both projects: fixed, or parametric when it holds placeholders (the same keys in the
  same places in both projects: that is the evidence);
- the same text split into other paragraphs, or other trailing punctuation: as equal;
- different: adaptive, the text of each project goes to the archive (with placeholders);
- only in one project: parametric when it holds placeholders (evidence of one project only,
  marked single_source), otherwise adaptive;
- tables and images (formulas are images) are never adaptive: when they differ, the one of the
  base project (R1) is kept as fixed and the difference is noted for the curator;
- any paragraph with a personal-data pattern left is never fixed or parametric.

Cover and signature are always parametric. The block's mode is the strongest of its paragraphs
(adaptive > parametric > fixed). No block keeps project text outside placeholders: adaptive
paragraphs keep only references to the archive and to the source sections.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from lxml import etree

from app.ingest.detect import fold
from app.library import privacy
from app.library.docx_blocks import Section, SplitDocument, w
from app.library.facts import Fact
from app.library.placeholders import substitute

MODES = ("fixed", "parametric", "adaptive")
STRENGTH = {m: i for i, m in enumerate(MODES)}


@dataclass
class Unit:
    project: str
    index: int  # position of the element in its section
    kind: str  # paragraph | table | image | empty
    original_ooxml: str
    ooxml: str  # with placeholders
    text: str  # with placeholders
    keys: list[str]
    hits: list[privacy.Hit]

    @property
    def norm(self) -> str:
        return fold(self.text).rstrip(" ;.:,")


@dataclass
class ProjectDoc:
    """One reference document of a project, split, with that project's facts."""

    project: str
    split: SplitDocument
    facts: list[Fact]
    section_ids: dict[int, str] = field(default_factory=dict)  # section order -> SourceSection id


@dataclass
class Entry:
    mode: str
    project: str  # whose OOXML and relationships
    units: dict[str, list[int]]  # project -> element indices in its source section
    text: str | None = None
    ooxml: str | None = None
    keys: list[str] = field(default_factory=list)
    single_source: bool = False
    note: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode, "project": self.project, "units": self.units, "text": self.text,
            "ooxml": self.ooxml, "keys": self.keys, "single_source": self.single_source,
            "note": self.note,
        }  # fmt: skip


@dataclass
class ProposedBlock:
    key: str
    doc_type: str
    kind: str  # cover | index | block | signature
    level: int
    title: str
    order: int
    mode: str
    entries: list[Entry]
    projects: list[str]
    source_refs: list[dict[str, Any]]
    rels: dict[str, dict[str, Any]]  # project -> {rId: relationship}
    notes: list[str]

    @property
    def required_keys(self) -> list[str]:
        return sorted({k for e in self.entries if e.mode == "parametric" for k in e.keys})

    @property
    def locked_ooxml(self) -> str | None:
        """The whole block as OOXML, when every paragraph is fixed or parametric."""
        if any(e.ooxml is None for e in self.entries):
            return None
        return "".join(e.ooxml or "" for e in self.entries)


@dataclass
class ArchiveText:
    """Text of one section of one project, for adaptive blocks (placeholders, data masked)."""

    project: str
    doc_type: str
    block_key: str
    order: int
    text: str
    section_id: str | None


# ---------------------------------------------------------------- units


def _unit(project: str, index: int, element: Any, facts: list[Fact], scope: str) -> Unit:
    sub = substitute(element, facts, scope)
    has_image = any(True for _ in element.iter(w("drawing"))) or any(
        True for _ in element.iter("{urn:schemas-microsoft-com:vml}imagedata")
    )
    if element.tag == w("tbl"):
        kind = "table"
    elif not sub.text.strip():
        kind = "image" if has_image else "empty"
    else:
        kind = "paragraph"
    return Unit(
        project, index, kind, etree.tostring(element, encoding="unicode"), sub.ooxml, sub.text,
        sub.keys, privacy.find(sub.text),
    )  # fmt: skip


def _units(doc: ProjectDoc, section: Section) -> list[Unit]:
    scope = "signature" if section.kind == "signature" else "document"
    return [_unit(doc.project, i, e, doc.facts, scope) for i, e in enumerate(section.elements)]


def _same(a: Unit, b: Unit) -> bool:
    return a.norm == b.norm and a.kind == b.kind


def _entry(unit: Unit, mode: str, **extra: Any) -> Entry:
    """A fixed or parametric entry from a unit (its OOXML with placeholders)."""
    if mode == "fixed":
        return Entry("fixed", unit.project, {unit.project: [unit.index]}, unit.text or None,
                     unit.original_ooxml, **extra)  # fmt: skip
    return Entry("parametric", unit.project, {unit.project: [unit.index]}, unit.text,
                 unit.ooxml, unit.keys, **extra)  # fmt: skip


def _proven(unit: Unit, other: Unit | None = None) -> Entry:
    """Entry for a unit equal in both projects (or with no other project to compare)."""
    if unit.hits:
        return _adaptive([unit] + ([other] if other else []),
                         note="Tem dados pessoais por identificar.")  # fmt: skip
    entry = _entry(unit, "parametric" if unit.keys else "fixed")
    if other is not None:
        entry.units[other.project] = [other.index]
    return entry


def _adaptive(units: list[Unit], note: str | None = None) -> Entry:
    by_project: dict[str, list[int]] = {}
    for u in units:
        by_project.setdefault(u.project, []).append(u.index)
    return Entry("adaptive", units[0].project, by_project, note=note)


def _lone(unit: Unit, where: str) -> Entry:
    """A unit that exists only in one project."""
    if unit.kind in ("empty", "image", "table") and not unit.hits:
        entry = _entry(unit, "parametric" if unit.keys else "fixed")
        if unit.kind != "empty":
            entry.note = f"Só em {where}."
        return entry
    if unit.keys and not unit.hits:
        return _entry(unit, "parametric", single_source=True,
                      note=f"Só em {where}: os valores da ficha foram trocados por marcadores, "
                           "com evidência de um só projeto.")  # fmt: skip
    return _adaptive([unit], note=f"Só em {where}.")


# ---------------------------------------------------------------- alignment


def _compare(base: list[Unit], other: list[Unit]) -> list[Entry]:
    a = [u for u in base if u.kind != "empty"]
    b = [u for u in other if u.kind != "empty"]
    matcher = SequenceMatcher(None, [(u.kind, u.norm) for u in a], [(u.kind, u.norm) for u in b],
                              autojunk=False)  # fmt: skip
    placed: dict[int, Entry] = {}  # base element index -> entry (to keep the base order)
    extra: list[Entry] = []  # entries that come only from the other project
    base_project, other_project = base[0].project, other[0].project
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        ra, rb = a[i1:i2], b[j1:j2]
        if tag == "equal":
            for x, y in zip(ra, rb, strict=True):
                placed[x.index] = _proven(x, y)
            continue
        if (
            ra
            and rb
            and fold(" ".join(u.text for u in ra)).rstrip(" ;.:,")
            == fold(" ".join(u.text for u in rb)).rstrip(" ;.:,")
        ):
            for x in ra:  # the same text, split into other paragraphs
                placed[x.index] = _proven(x)
                placed[x.index].units[other_project] = [u.index for u in rb]
            continue
        paragraphs_a = [u for u in ra if u.kind == "paragraph"]
        paragraphs_b = [u for u in rb if u.kind == "paragraph"]
        for x in ra:
            if x.kind in ("table", "image"):
                twin = next((u for u in rb if u.kind == x.kind), None)
                entry = _lone(x, base_project) if twin is None else _proven(x, twin)
                if twin is not None and entry.mode != "adaptive":
                    entry.note = (f"Diferente em {other_project}: fica a de {base_project} "
                                  "(a confirmar).")  # fmt: skip
                placed[x.index] = entry
        if paragraphs_a and paragraphs_b:
            placed[paragraphs_a[0].index] = _adaptive(
                paragraphs_a + paragraphs_b,
                note=f"Texto diferente em {base_project} e {other_project}.",
            )
            for x in paragraphs_a[1:]:
                placed[x.index] = Entry("adaptive", base_project, {}, note="(continuação)")
        elif paragraphs_a:
            for x in paragraphs_a:
                placed[x.index] = _lone(x, base_project)
        elif paragraphs_b:
            extra += [_lone(y, other_project) for y in paragraphs_b]
        for y in rb:
            if y.kind in ("table", "image") and not any(u.kind == y.kind for u in ra):
                extra.append(_lone(y, other_project))
    # empty paragraphs of the base keep their place (layout)
    for u in base:
        if u.kind == "empty" and u.index not in placed:
            placed[u.index] = _entry(u, "fixed")
    ordered = [placed[i] for i in sorted(placed) if placed[i].note != "(continuação)"]
    return ordered + extra


def _single(units: list[Unit], where: str) -> list[Entry]:
    entries = []
    for i, u in enumerate(units):
        if i == 0 and u.kind != "empty" and not u.hits and not u.keys:
            entries.append(_entry(u, "fixed", note=f"Título; bloco só em {where}."))
        else:
            entries.append(_lone(u, where))
    return entries


def _forced_parametric(units: list[Unit], other: list[Unit] | None) -> list[Entry]:
    """Cover and signature: the base text with placeholders, always parametric."""
    entries = []
    for u in units:
        if u.hits:
            entries.append(
                _adaptive([u], note="Dados pessoais por identificar na capa/assinatura.")
            )
        else:
            entries.append(_entry(u, "parametric" if u.keys else "fixed"))
    if other:
        missing = {k for u in other for k in u.keys} - {k for u in units for k in u.keys}
        if missing:
            entries[-1].note = "Também em outro projeto: " + ", ".join(sorted(missing))
    return entries


# ---------------------------------------------------------------- blocks


def _mode(entries: list[Entry], kind: str) -> str:
    if kind in ("cover", "signature"):
        return "parametric"
    return max((e.mode for e in entries), key=lambda m: STRENGTH[m], default="fixed")


def _rels(entries: list[Entry], sections: dict[str, Section]) -> dict[str, dict[str, Any]]:
    used: dict[str, dict[str, Any]] = {}
    for e in entries:
        if e.ooxml is None:
            continue
        section = sections[e.project]
        for rid, rel in section.rels.items():
            if f'"{rid}"' in e.ooxml:
                used.setdefault(e.project, {})[rid] = vars(rel)
    return used


def classify(
    doc_type: str, docs: list[ProjectDoc]
) -> tuple[list[ProposedBlock], list[ArchiveText]]:
    """Blocks proposed from the same document type of several reference projects."""
    if not docs:
        return [], []
    order = _merged_keys([d.split.sections for d in docs])
    by_key = {d.project: {s.key: s for s in d.split.sections} for d in docs}
    blocks: list[ProposedBlock] = []
    archive: list[ArchiveText] = []
    for n, key in enumerate(order, start=1):
        present = [d for d in docs if key in by_key[d.project]]
        sections = {d.project: by_key[d.project][key] for d in present}
        first = sections[present[0].project]
        units = {d.project: _units(d, sections[d.project]) for d in present}
        where = present[0].project
        if first.kind in ("cover", "signature"):
            other = units[present[1].project] if len(present) > 1 else None
            entries = _forced_parametric(units[where], other)
        elif first.kind == "index":
            entries = [Entry("fixed", where, {where: list(range(len(first.elements)))}, None,
                             first.ooxml, note="Índice: o Word atualiza-o ao abrir.")]  # fmt: skip
        elif len(present) == 1:
            entries = _single(units[where], where)
        else:
            entries = _compare(units[present[0].project], units[present[1].project])
        notes = [e.note for e in entries if e.note and not e.note.startswith("Título")]
        if len(present) == 1:
            notes.insert(0, f"Bloco só em {where}: candidato, a regra de ativação decide.")
        block_key = f"{base_specialty()}.{doc_type.lower()}.{key}"
        blocks.append(ProposedBlock(
            key=block_key, doc_type=doc_type, kind=first.kind, level=first.level,
            title=first.title, order=n, mode=_mode(entries, first.kind), entries=entries,
            projects=[d.project for d in present],
            source_refs=[_source_ref(d, sections[d.project]) for d in present],
            rels=_rels(entries, sections), notes=list(dict.fromkeys(notes)),
        ))  # fmt: skip
        if any(e.mode == "adaptive" for e in entries):
            for d in present:
                text = "\n".join(u.text for u in units[d.project] if u.text.strip())
                section_id = d.section_ids.get(sections[d.project].order)
                archive.append(
                    ArchiveText(d.project, doc_type, block_key, n, privacy.mask(text), section_id)
                )
    return blocks, archive


def _source_ref(doc: ProjectDoc, section: Section) -> dict[str, Any]:
    return {"project": doc.project, "section_id": doc.section_ids.get(section.order),
            "order": section.order}  # fmt: skip


def base_specialty() -> str:
    return "ele"


def _merged_keys(section_lists: list[list[Section]]) -> list[str]:
    """Section keys of every project, in document order (the base project's order first)."""
    merged = [s.key for s in section_lists[0]]
    for sections in section_lists[1:]:
        keys = [s.key for s in sections]
        matcher = SequenceMatcher(None, merged, keys, autojunk=False)
        out: list[str] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            out += merged[i1:i2]
            if tag in ("insert", "replace"):
                out += [k for k in keys[j1:j2] if k not in merged]
        merged = list(dict.fromkeys(out))
    return merged
