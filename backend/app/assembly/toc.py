"""The index (TOC field) of an assembled document, written from its own titles.

The index block is the template project's, with that project's cached entries: the sections
left out, the ones that are new and the titles changed by hand would show until Word updates
the field. Here the entries are written again from the titles of the document:
- titles: paragraphs with an outline level inside the field's range (`\\o "1-3"`), with text;
- each title keeps its own `_Toc` bookmark, or gets a new one (`_TocMaestro<n>`);
- the number of a numbered title is computed from numbering.xml (decimal levels);
- each entry is a copy of the template's first entry of its level (styles, tabs, runs).
The page numbers are left empty: app.export.toc writes them from a LibreOffice PDF, or Word
updates the field when the file is opened (updateFields).
"""

import copy
import re
from dataclasses import dataclass
from typing import Any

from lxml import etree

from app.library.docx_blocks import w

_LEVELS = re.compile(r'\\o\s+"(\d)-(\d)"')
TOC_BOOKMARK = "_TocMaestro"


@dataclass
class Title:
    paragraph: Any
    level: int  # 1, 2, 3…
    text: str
    number: str
    anchor: str = ""


def _text(p: Any) -> str:
    return re.sub(r"\s+", " ", "".join(t.text or "" for t in p.iter(w("t")))).strip()


def _style_levels(styles: bytes | None) -> tuple[dict[str, int], dict[str, tuple[str, str]]]:
    """Outline level and numbering (numId, ilvl) of each paragraph style, through basedOn."""
    if not styles:
        return {}, {}
    root = etree.fromstring(styles)
    own: dict[str, tuple[int | None, tuple[str, str] | None, str | None]] = {}
    for style in root.iter(w("style")):
        if style.get(w("type")) != "paragraph":
            continue
        ppr = style.find(w("pPr"))
        level: int | None = None
        num: tuple[str, str] | None = None
        if ppr is not None:
            outline = ppr.find(w("outlineLvl"))
            if outline is not None:
                level = int(outline.get(w("val"), "9"))
            num_id = ppr.find(f"{w('numPr')}/{w('numId')}")
            if num_id is not None:
                ilvl = ppr.find(f"{w('numPr')}/{w('ilvl')}")
                num = (
                    num_id.get(w("val"), "0"),
                    ilvl.get(w("val"), "0") if ilvl is not None else "0",
                )
        based = style.find(w("basedOn"))
        own[style.get(w("styleId"), "")] = (
            level,
            num,
            based.get(w("val")) if based is not None else None,
        )

    def resolve(sid: str, index: int, seen: frozenset[str] = frozenset()) -> Any:
        if sid not in own or sid in seen:
            return None
        value = own[sid][index]
        parent = own[sid][2]
        return (
            value if value is not None or parent is None else resolve(parent, index, seen | {sid})
        )

    levels = {sid: lv for sid in own if (lv := resolve(sid, 0)) is not None}
    nums = {sid: n for sid in own if (n := resolve(sid, 1)) is not None}
    return levels, nums


class _Numbering:
    """Decimal multilevel numbers of the titles, as Word shows them (counters per list)."""

    def __init__(self, numbering: bytes | None) -> None:
        self.levels: dict[str, dict[int, tuple[str, str, int]]] = {}  # numId -> ilvl -> fmt
        self.abstract_of: dict[str, str] = {}
        self.counters: dict[str, dict[int, int]] = {}
        if not numbering:
            return
        root = etree.fromstring(numbering)
        abstracts: dict[str, dict[int, tuple[str, str, int]]] = {}
        for ab in root.iter(w("abstractNum")):
            lv: dict[int, tuple[str, str, int]] = {}
            for lvl in ab.findall(w("lvl")):
                fmt, text, start = (
                    lvl.find(w("numFmt")),
                    lvl.find(w("lvlText")),
                    lvl.find(w("start")),
                )
                lv[int(lvl.get(w("ilvl"), "0"))] = (
                    fmt.get(w("val"), "decimal") if fmt is not None else "decimal",
                    text.get(w("val"), "") if text is not None else "",
                    int(start.get(w("val"), "1")) if start is not None else 1,
                )
            abstracts[ab.get(w("abstractNumId"), "")] = lv
        for num in root.iter(w("num")):
            ab_id = num.find(w("abstractNumId"))
            target = ab_id.get(w("val"), "") if ab_id is not None else ""
            if target in abstracts:
                self.abstract_of[num.get(w("numId"), "")] = target
                self.levels[num.get(w("numId"), "")] = abstracts[target]

    def next(self, num_id: str, ilvl: int) -> str:
        levels = self.levels.get(num_id)
        if not levels or ilvl not in levels or levels[ilvl][0] not in ("decimal", "none"):
            return ""
        counters = self.counters.setdefault(self.abstract_of[num_id], {})
        counters[ilvl] = counters.get(ilvl, levels[ilvl][2] - 1) + 1
        for deeper in [k for k in counters if k > ilvl]:
            del counters[deeper]
        return re.sub(
            r"%(\d)",
            lambda m: str(
                counters.get(int(m.group(1)) - 1, levels.get(int(m.group(1)) - 1, ("", "", 1))[2])
            ),
            levels[ilvl][1],
        )


def _field_bounds(body: Any) -> tuple[Any, Any, list[Any]] | None:
    """(paragraph with the TOC field's begin, paragraph with its end, cached entries)."""
    paragraphs = list(body.iter(w("p")))
    for i, p in enumerate(paragraphs):
        instr = "".join(t.text or "" for t in p.iter(w("instrText")))
        if not re.match(r"\s*TOC\b", instr):
            continue
        depth = 0
        for j in range(i, len(paragraphs)):
            for fc in paragraphs[j].iter(w("fldChar")):
                kind = fc.get(w("fldCharType"))
                depth += 1 if kind == "begin" else -1 if kind == "end" else 0
                if depth == 0:
                    entries = [
                        q for q in paragraphs[i : j + 1] if q.find(w("hyperlink")) is not None
                    ]
                    return p, paragraphs[j], entries
        return None
    return None


def _titles(
    body: Any,
    after: Any,
    styles: bytes | None,
    numbering: bytes | None,
    levels_range: tuple[int, int],
) -> list[Title]:
    style_levels, style_nums = _style_levels(styles)
    numbers = _Numbering(numbering)
    out: list[Title] = []
    started = False
    for p in body.iter(w("p")):
        if p is after:
            started = True
            continue
        ppr = p.find(w("pPr"))
        style = ppr.find(w("pStyle")) if ppr is not None else None
        sid = style.get(w("val")) if style is not None else None
        outline = ppr.find(w("outlineLvl")) if ppr is not None else None
        level = (
            int(outline.get(w("val"))) if outline is not None else style_levels.get(sid or "", 9)
        ) + 1
        num_pr = ppr.find(w("numPr")) if ppr is not None else None
        num = style_nums.get(sid or "")
        if num_pr is not None and num_pr.find(w("numId")) is not None:
            ilvl = num_pr.find(w("ilvl"))
            num = (
                num_pr.find(w("numId")).get(w("val")),
                ilvl.get(w("val")) if ilvl is not None else (num[1] if num else "0"),
            )
        text = _text(p)
        if level > 9 or not text:
            continue
        number = numbers.next(num[0], int(num[1])) if num and num[0] != "0" else ""
        if started and levels_range[0] <= level <= levels_range[1]:
            out.append(Title(p, level, text, number))
    return out


def _bookmarks(root: Any, titles: list[Title], cached: set[str]) -> None:
    """Each title's own _Toc bookmark (the one the cached index points to, if any), or a new one
    around its text."""
    ids = [int(i) for el in root.iter(w("bookmarkStart")) if (i := el.get(w("id")) or "").isdigit()]
    next_id = max(ids, default=0) + 1
    used: set[str] = set()
    for n, title in enumerate(titles, 1):
        mine = [
            el.get(w("name"))
            for el in title.paragraph.iter(w("bookmarkStart"))
            if (el.get(w("name")) or "").startswith("_Toc")
        ]
        free = [m for m in mine if m not in used]
        name = next((m for m in free if m in cached), free[0] if free else None)
        if name is None:
            name = f"{TOC_BOOKMARK}{n:04d}"
            start = etree.Element(w("bookmarkStart"))
            start.set(w("id"), str(next_id))
            start.set(w("name"), name)
            end = etree.Element(w("bookmarkEnd"))
            end.set(w("id"), str(next_id))
            next_id += 1
            ppr = title.paragraph.find(w("pPr"))
            title.paragraph.insert(0 if ppr is None else title.paragraph.index(ppr) + 1, start)
            title.paragraph.append(end)
        used.add(name)
        title.anchor = name


def _set_text(run: Any, text: str) -> None:
    for t in run.findall(w("t")):
        run.remove(t)
    el = etree.SubElement(run, w("t"))
    el.text = text
    el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def _entry(prototype: Any, title: Title) -> Any:
    """A copy of the template's entry, with the title's number, text and anchor."""
    p = copy.deepcopy(prototype)
    for child in list(p):  # the field's own begin/instr/separate stay with the first entry only
        if child.tag not in (w("pPr"), w("hyperlink")):
            p.remove(child)
    link = p.find(w("hyperlink"))
    link.set(w("anchor"), title.anchor)
    runs = link.findall(w("r"))
    tabs = [i for i, r in enumerate(runs) if r.find(w("tab")) is not None]
    first_field = next(
        (i for i, r in enumerate(runs) if r.find(w("fldChar")) is not None), len(runs)
    )
    tabs = [i for i in tabs if i < first_field]
    if len(tabs) >= 2:
        number_runs, title_runs = runs[: tabs[0]], runs[tabs[0] + 1 : tabs[-1]]
    else:  # an entry without a number in the template
        number_runs, title_runs = [], runs[: tabs[0]] if tabs else runs[:first_field]
    for r in number_runs[1:] + title_runs[1:]:
        link.remove(r)
    if number_runs and title.number:
        _set_text(number_runs[0], title.number)
    elif number_runs:
        link.remove(number_runs[0])
        link.remove(runs[tabs[0]])
    if title_runs:
        _set_text(title_runs[0], title.text)
    for instr in link.iter(w("instrText")):
        if "PAGEREF" in (instr.text or ""):
            instr.text = f" PAGEREF {title.anchor} \\h "
    set_page(link, "")
    return p


def set_page(link: Any, page: str) -> None:
    """The cached result of the PAGEREF field of an entry."""
    runs = link.findall(w("r"))
    inside = False
    written = False
    for r in runs:
        fc = r.find(w("fldChar"))
        kind = fc.get(w("fldCharType")) if fc is not None else None
        if kind == "separate":
            inside = True
        elif kind == "end":
            inside = False
        elif inside and r.find(w("t")) is not None:
            if written:
                link.remove(r)
            else:
                _set_text(r, page)
                written = True


def rebuild(document_xml: bytes, styles: bytes | None, numbering: bytes | None) -> bytes:
    """The TOC field's entries written from the document's own titles (no page numbers yet)."""
    root = etree.fromstring(document_xml)
    body = root.find(w("body"))
    bounds = _field_bounds(body) if body is not None else None
    if bounds is None:
        return document_xml
    begin, end, cached = bounds
    if not cached:
        return document_xml
    instr = "".join(t.text or "" for t in begin.iter(w("instrText")))
    m = _LEVELS.search(instr)
    levels_range = (int(m.group(1)), int(m.group(2))) if m else (1, 3)
    titles = _titles(body, end, styles, numbering, levels_range)
    if not titles:
        return document_xml
    _bookmarks(root, titles, {h.get(w("anchor")) for p in cached for h in p.iter(w("hyperlink"))})
    prototypes: dict[str, Any] = {}
    for p in cached:
        style = p.find(f"{w('pPr')}/{w('pStyle')}")
        prototypes.setdefault(style.get(w("val")) if style is not None else "", p)
    by_level = sorted(prototypes.values(), key=lambda p: _style_level(p, prototypes))
    head = [c for c in begin if c.tag != w("pPr") and c.tag != w("hyperlink")]
    head = head[: next((i for i, c in enumerate(head) if _is_separate(c)), len(head) - 1) + 1]
    entries = []
    for title in titles:
        prototype = _prototype_for(title.level, prototypes, by_level)
        entries.append(_entry(prototype, title))
    ppr = entries[0].find(w("pPr"))
    at = 0 if ppr is None else entries[0].index(ppr) + 1
    for i, run in enumerate(head):
        entries[0].insert(at + i, copy.deepcopy(run))
    parent = begin.getparent()
    position = parent.index(begin)
    for p in cached:
        if p is end and p is not begin:  # keeps the field's end, not its old entry
            for link in p.findall(w("hyperlink")):
                p.remove(link)
        else:
            p.getparent().remove(p)
    for i, p in enumerate(entries):
        parent.insert(position + i, p)
    if end is begin:  # the field ended in the first entry: close it after the last
        closing = etree.SubElement(entries[-1], w("r"))
        etree.SubElement(closing, w("fldChar")).set(w("fldCharType"), "end")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _is_separate(run: Any) -> bool:
    fc = run.find(w("fldChar"))
    return fc is not None and fc.get(w("fldCharType")) == "separate"


def _style_level(p: Any, prototypes: dict[str, Any]) -> int:
    style = p.find(f"{w('pPr')}/{w('pStyle')}")
    digits = re.findall(r"\d+", style.get(w("val")) if style is not None else "")
    return int(digits[-1]) if digits else 99


def _prototype_for(level: int, prototypes: dict[str, Any], by_level: list[Any]) -> Any:
    """The template entry of the same TOC level (style «toc N»), or the nearest one above."""
    candidates = [p for p in by_level if _style_level(p, prototypes) <= level]
    return candidates[-1] if candidates else by_level[0]
