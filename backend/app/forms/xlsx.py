"""Cell-level editing of an .xlsx/.xlsm package, in the sheet XML itself.

openpyxl would rewrite the whole workbook and lose what it does not support (the data validation
extension with the DGEG lists, ActiveX controls). Here only the edited cells change: VBA, styles,
validations and drawings stay byte for byte.

Only the parts that were changed are written again ("dirty"); reading a part (e.g. the workbook
to find a sheet) does not change it. Every other part keeps its content, its place and its date
in the zip; its compressed stream may differ (zlib), never its bytes once unzipped (Phase 6).
"""

import io
import posixpath
import re
import zipfile
from typing import Any

from lxml import etree

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SST = "xl/sharedStrings.xml"
CELL = re.compile(r"([A-Z]+)(\d+)$")


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def column_number(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def _split(ref: str) -> tuple[int, int]:
    m = CELL.match(ref)
    if m is None:
        raise ValueError(f"célula inválida: {ref}")
    return column_number(m.group(1)), int(m.group(2))


class Workbook:
    """The parts of a package, with the sheets parsed on demand."""

    def __init__(self, data: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.infos = z.infolist()
            self.parts = {i.filename: z.read(i.filename) for i in self.infos}
        self._trees: dict[str, Any] = {}
        self._dirty: set[str] = set()

    def tree(self, part: str) -> Any:
        if part not in self._trees:
            self._trees[part] = etree.fromstring(self.parts[part])
        return self._trees[part]

    def touch(self, part: str) -> Any:
        """The tree of a part about to change: it will be written again."""
        self._dirty.add(part)
        return self.tree(part)

    def sheet_part(self, name: str) -> str:
        book = self.tree("xl/workbook.xml")
        rels = self.tree("xl/_rels/workbook.xml.rels")
        for sheet in book.iter(q("sheet")):
            if sheet.get("name") == name:
                rid = sheet.get(f"{{{REL_NS}}}id")
                for rel in rels.iter(f"{{{PKG_REL_NS}}}Relationship"):
                    if rel.get("Id") == rid:
                        return posixpath.normpath(posixpath.join("xl", rel.get("Target", "")))
        raise KeyError(f"folha inexistente: {name}")

    def sheet_parts(self) -> list[str]:
        return [p for p in self.parts if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", p)]

    def cell(self, part: str, ref: str, create: bool = False) -> Any:
        sheet_data = (self.touch(part) if create else self.tree(part)).find(q("sheetData"))
        col, row_n = _split(ref)
        row = None
        for r in sheet_data.iter(q("row")):
            n = int(r.get("r"))
            if n == row_n:
                row = r
                break
            if n > row_n:
                if not create:
                    return None
                row = etree.Element(q("row"), r=str(row_n))
                r.addprevious(row)
                break
        if row is None:
            if not create:
                return None
            row = etree.SubElement(sheet_data, q("row"), r=str(row_n))
        for c in row.iter(q("c")):
            c_col, _ = _split(str(c.get("r")))
            if c_col == col:
                return c
            if c_col > col:
                if not create:
                    return None
                new = etree.Element(q("c"), r=ref)
                c.addprevious(new)
                return new
        return etree.SubElement(row, q("c"), r=ref) if create else None

    def put(self, part: str, ref: str, value: Any, keep_formula: bool = True) -> None:
        """Write a value (None clears it). A formula stays, with the value as its cached result."""
        c = self.cell(part, ref, create=value is not None)
        if c is None:
            return
        self.touch(part)
        formula = c.find(q("f")) if keep_formula else None
        for child in list(c):
            if child is not formula:
                c.remove(child)
        c.attrib.pop("t", None)
        if value is None:
            return
        if isinstance(value, bool):
            c.set("t", "b")
            etree.SubElement(c, q("v")).text = "1" if value else "0"
        elif isinstance(value, int | float):
            etree.SubElement(c, q("v")).text = (
                repr(value) if isinstance(value, float) else str(value)
            )
        elif formula is not None:
            c.set("t", "str")
            etree.SubElement(c, q("v")).text = str(value)
        else:
            c.set("t", "inlineStr")
            t = etree.SubElement(etree.SubElement(c, q("is")), q("t"))
            t.text = str(value)
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    def drop_hyperlinks(self, part: str, refs: set[str]) -> None:
        """Remove the links of these cells (e.g. mailto: of an email) and their relationships."""
        sheet = self.tree(part)
        links = sheet.find(q("hyperlinks"))
        if links is None:
            return
        self.touch(part)
        dropped = set()
        for link in list(links):
            if link.get("ref") in refs:
                dropped.add(link.get(f"{{{REL_NS}}}id"))
                links.remove(link)
        if not len(links):
            sheet.remove(links)
        rels_part = posixpath.join(posixpath.dirname(part), "_rels",
                                   posixpath.basename(part) + ".rels")  # fmt: skip
        if dropped and rels_part in self.parts:
            rels = self.touch(rels_part)
            for rel in list(rels):
                if rel.get("Id") in dropped:
                    rels.remove(rel)

    def clear_cached_results(self, part: str) -> None:
        """Formula cells keep the formula and lose the result computed for another project."""
        for c in self.touch(part).iter(q("c")):
            if c.find(q("f")) is not None:
                for v in c.findall(q("v")):
                    c.remove(v)
                c.attrib.pop("t", None)

    def recalculate_on_open(self) -> None:
        """Excel recalculates the formulas when the file opens (only written if not yet set)."""
        book = self.tree("xl/workbook.xml")
        calc = book.find(q("calcPr"))
        if calc is not None and calc.get("fullCalcOnLoad") in ("1", "true"):
            return
        book = self.touch("xl/workbook.xml")
        if calc is None:
            calc = etree.SubElement(book, q("calcPr"))
        calc.set("fullCalcOnLoad", "1")

    def print_header(self, part: str, text: str) -> None:
        """A text in the centre of the printed header of every page (the draft's watermark).

        It lives in the sheet XML (<headerFooter>), placed where the schema wants it.
        """
        sheet = self.touch(part)
        header = sheet.find(q("headerFooter"))
        if header is None:
            header = etree.Element(q("headerFooter"))
            before = next((sheet.find(q(t)) for t in reversed(_BEFORE_HEADER)
                           if sheet.find(q(t)) is not None), None)  # fmt: skip
            if before is not None:
                before.addnext(header)
            else:
                after = next((sheet.find(q(t)) for t in _AFTER_HEADER
                              if sheet.find(q(t)) is not None), None)  # fmt: skip
                if after is not None:
                    after.addprevious(header)
                else:
                    sheet.append(header)
        for tag in ("oddHeader", "firstHeader", "evenHeader"):
            el = header.find(q(tag))
            if el is None and tag != "oddHeader":
                continue
            if el is None:
                el = etree.Element(q(tag))
                header.insert(0, el)
            el.text = f'&C&"-,Bold"&16{text}'

    def prune_shared_strings(self) -> None:
        """Drop the shared strings no cell uses (the values of the project a template came from)."""
        if SST not in self.parts:
            return
        sst = self.touch(SST)
        items = sst.findall(q("si"))
        cells = [c for p in self.sheet_parts() for c in self.touch(p).iter(q("c"))
                 if c.get("t") == "s"]  # fmt: skip
        used = sorted({int(c.findtext(q("v"))) for c in cells})
        new_index = {old: new for new, old in enumerate(used)}
        for c in cells:
            v = c.find(q("v"))
            v.text = str(new_index[int(v.text)])
        for i, si in enumerate(items):
            if i not in new_index:
                sst.remove(si)
        sst.set("count", str(len(cells)))
        sst.set("uniqueCount", str(len(used)))

    def to_bytes(self) -> bytes:
        changed = {
            part: etree.tostring(self._trees[part], xml_declaration=True, encoding="UTF-8",
                                 standalone=True)
            for part in self._dirty
        }  # fmt: skip
        return replace_parts(self.infos, {**self.parts, **changed})


# CT_Worksheet: what comes before and after <headerFooter>
_BEFORE_HEADER = ("printOptions", "pageMargins", "pageSetup")
_AFTER_HEADER = ("rowBreaks", "colBreaks", "customProperties", "cellWatches", "ignoredErrors",
                 "smartTags", "drawing", "legacyDrawing", "legacyDrawingHF", "drawingHF", "picture",
                 "oleObjects", "controls", "webPublishItems", "tableParts", "extLst")  # fmt: skip


def replace_parts(infos: list[zipfile.ZipInfo], parts: dict[str, bytes]) -> bytes:
    """A package with the same entries, in the same order and with the same dates."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info in infos:
            z.writestr(info, parts[info.filename], compress_type=info.compress_type)
    return out.getvalue()
