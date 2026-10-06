""".docx of an assembled document: the draft (Phase 4) and the export (Phase 6, app.export).

Built on the package of the template document (styles, numbering, theme, headers) [A CONFIRMAR]:
- fixed paragraphs: the block's original OOXML;
- parametric: the same OOXML, each {{v:key}} replaced in the w:t it is in (the run keeps its
  formatting); missing values are written as "[falta: …]";
- adaptive: the current version's paragraphs, with the paragraph properties of the source text;
- an entry changed by hand (an unlocked fixed block, an edited parametric one) leaves as text
  with the paragraph properties of the source (Phase 4 decision [A CONFIRMAR]);
- fragments of another reference project: their relationships are copied into the package
  (media from S3, new relationship ids); drawing ids are numbered again so none repeats;
- headers and footers: the template project's technician, date and revision (R00) become the
  target's (the date only when the técnico wrote it, P8);
- the draft carries a watermark in every header; the document properties name TUU, not people;
- Word updates the fields (the index) when the file is opened.
Inactive sections are left out. Personal values are only written here, in the backend.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape
from typing import Any

from lxml import etree
from sqlalchemy.orm import Session

from app.assembly.assemble import PLACEHOLDER, omitted
from app.assembly.values import ValueSource, label
from app.library.docx_blocks import DOCUMENT, DOCUMENT_RELS, PKG_R, rebuild, w
from app.library.facts import Fact, signature_facts, text_fact
from app.library.placeholders import substitute
from app.library.sources import media_key
from app.models import Document, SourceDocument, SourceSection, TemplateBlock
from app.storage import ObjectStore

REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MEDIA_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg", "gif": "image/gif",
               "emf": "image/x-emf", "wmf": "image/x-wmf", "bmp": "image/bmp",
               "tif": "image/tiff", "tiff": "image/tiff", "svg": "image/svg+xml"}  # fmt: skip
_MONTH_YEAR = re.compile(
    r"(?i)(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|"
    r"novembro|dezembro)\s*[/|de ]*\s*\d{4}"
)
_REVISION = re.compile(r"\bR\d{2}\b")  # the revision in the header of the TUU documents
COMPANY = "TUU – Building Design Management, Lda"  # noqa: RUF001 (as in the documents)
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC = "http://purl.org/dc/elements/1.1/"
DCTERMS = "http://purl.org/dc/terms/"
EXT = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
VML = "urn:schemas-microsoft-com:vml"
OFFICE = "urn:schemas-microsoft-com:office:office"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


@dataclass
class Options:
    """What the export adds to the draft of Phase 4."""

    revision: str | None = None  # R00, R01… in the header
    header_date: str | None = None  # only when the técnico wrote it (P8)
    watermark: str | None = None  # "RASCUNHO — não aprovado" on every page of a draft
    title: str | None = None  # document properties
    subject: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def _value_text(values: ValueSource, key: str, extra: dict[str, str] | None = None) -> str:
    if extra and key in extra:
        return extra[key]
    r = values.resolve(key)
    return f"[falta: {label(key)}]" if r.missing else (r.text or "")


def fill(ooxml: str, values: ValueSource, extra: dict[str, str] | None = None) -> str:
    """Write the values of the placeholders into an OOXML fragment (inside its w:t)."""
    return PLACEHOLDER.sub(
        lambda m: escape(_value_text(values, m.group(1), extra), quote=False), ooxml
    )


class _Package:
    """The template package, with parts to add or replace."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.zip = zipfile.ZipFile(io.BytesIO(data))
        self.parts: dict[str, bytes] = {}
        self.rels = etree.fromstring(self.zip.read(DOCUMENT_RELS))
        self.types = etree.fromstring(self.zip.read("[Content_Types].xml"))
        self.nsmap = etree.fromstring(self.zip.read(DOCUMENT)).nsmap
        self._next = 1
        self._copied: dict[str, str] = {}  # sha256 -> new rId
        self._changed: set[str] = set()  # relationships and content types: written only if changed

    def add_media(self, rel: dict[str, Any], blob: bytes) -> str:
        sha = rel["sha256"]
        if sha in self._copied:
            return self._copied[sha]
        ext = rel["target"].rsplit(".", 1)[-1].lower()
        name = f"media/imported_{sha[:16]}.{ext}"
        self.parts[f"word/{name}"] = blob
        rid = f"rIdImported{self._next}"
        self._next += 1
        etree.SubElement(self.rels, f"{{{PKG_R}}}Relationship", Id=rid,
                         Type=REL_TYPE + rel["type"], Target=name)  # fmt: skip
        self._changed.add(DOCUMENT_RELS)
        if ext in MEDIA_TYPES and not any(
            d.get("Extension", "").lower() == ext for d in self.types.iter(f"{{{CT}}}Default")
        ):
            etree.SubElement(self.types, f"{{{CT}}}Default", Extension=ext,
                             ContentType=MEDIA_TYPES[ext])  # fmt: skip
            self._changed.add("[Content_Types].xml")
        self._copied[sha] = rid
        return rid

    def write(self, document_xml: bytes) -> bytes:
        self.parts[DOCUMENT] = document_xml
        if DOCUMENT_RELS in self._changed:
            self.parts[DOCUMENT_RELS] = etree.tostring(
                self.rels, xml_declaration=True, encoding="UTF-8", standalone=True
            )
        if "[Content_Types].xml" in self._changed:
            self.parts["[Content_Types].xml"] = etree.tostring(
                self.types, xml_declaration=True, encoding="UTF-8", standalone=True
            )
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            names = [i.filename for i in self.zip.infolist()]
            for info in self.zip.infolist():
                dst.writestr(info, self.parts.get(info.filename, self.zip.read(info.filename)))
            for name, blob in self.parts.items():
                if name not in names:
                    dst.writestr(name, blob)
        return out.getvalue()


def _elements(package: _Package, fragment: str) -> list[Any]:
    decl = " ".join(f'xmlns:{p}="{u}"' if p else f'xmlns="{u}"' for p, u in package.nsmap.items())
    return list(etree.fromstring(f"<wrap {decl}>{fragment}</wrap>"))


def _remap(package: _Package, store: ObjectStore, fragment: str, rels: dict[str, Any]) -> str:
    """Relationship ids of another project's fragment, made valid in the template package."""
    for rid in set(re.findall(r'r:(?:embed|id|link)="([^"]+)"', fragment)):
        rel = rels.get(rid)
        if rel is None or rel.get("external") or not rel.get("sha256"):
            continue
        new = package.add_media(rel, store.get(media_key(rel["sha256"])))
        fragment = re.sub(rf'(r:(?:embed|id|link))="{re.escape(rid)}"', rf'\1="{new}"', fragment)
    return fragment


def _paragraph(text: str, ppr: str) -> str:
    return (f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{escape(text, quote=False)}</w:t></w:r>"
            "</w:p>")  # fmt: skip


def _source_ppr(db: Session, package: _Package, block: TemplateBlock, entry: dict[str, Any]) -> str:
    """Paragraph properties of the first source paragraph of an adaptive entry."""
    for ref in block.source_refs:
        idx = entry["units"].get(ref["project"])
        if not idx or not ref.get("section_id"):
            continue
        section = db.get(SourceSection, ref["section_id"])
        if section is None:
            continue
        elements = _elements(package, section.ooxml)
        if idx[0] < len(elements):
            ppr = elements[idx[0]].find(w("pPr"))
            if ppr is not None:
                ppr = etree.fromstring(etree.tostring(ppr))
                for child in ppr.findall(w("sectPr")):
                    ppr.remove(child)
                return etree.tostring(ppr, encoding="unicode")
    return ""


def _text_of(node: dict[str, Any], values: ValueSource) -> str:
    """The text of a paragraph node. A value is written as the node has it (a value changed by
    hand stays changed, COE-01), except a personal one, masked in the content: resolved here."""
    out = []
    for child in node.get("content") or []:
        mark = next((m for m in child.get("marks") or [] if m["type"] == "value"), None)
        if mark is not None and (mark["attrs"].get("personal") or mark["attrs"].get("missing")):
            out.append(_value_text(values, mark["attrs"]["key"]))
        else:
            out.append(child.get("text", ""))
    return "".join(out)


def _lines(node: dict[str, Any], values: ValueSource) -> list[str]:
    """The paragraphs of a node: a locked node holds several."""
    if node.get("type") == "locked":
        return [_text_of(p, values) for p in node.get("content") or []]
    return [_text_of(node, values)]


def by_entry(nodes: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        attrs = node.get("attrs") or {}
        if "entry" in attrs and not attrs.get("generated"):
            out.setdefault(attrs["entry"], []).append(node)
    return out


def _headers(package: _Package, template: SourceDocument, db: Session, values: ValueSource,
             options: Options) -> None:  # fmt: skip
    """Technician, date and revision of the template project in headers and footers become the
    target's: the técnico of the profile, the date only if they wrote it (P8), R<nn>."""
    signature = next((s for s in template.sections if s.kind == "signature"), None)
    facts: list[Fact] = signature_facts(signature.text.splitlines()) if signature else []
    facts = [f for f in facts if f.key == "tec.nome"]
    date = Fact("doc.data", "mês de ano", _MONTH_YEAR)
    upper = [text_fact(f.key, f.value.upper()) for f in facts]
    facts += [f for f in upper if f] + [date]
    if options.revision:
        facts.append(Fact("doc.revisao", "R00", _REVISION))
    extra = {"doc.data": options.header_date or "", **options.extra}
    if options.revision:
        extra["doc.revisao"] = options.revision
    for name in package.zip.namelist():
        if not re.fullmatch(r"word/(header|footer)\d*\.xml", name):
            continue
        root = etree.fromstring(package.zip.read(name))
        changed = False
        for p in list(root.iter(w("p"))):
            sub = substitute(p, facts)
            parent = p.getparent()
            if sub.keys and parent is not None:
                parent.replace(p, sub.element)
                changed = True
        if name.startswith("word/header") and options.watermark:
            _watermark(root, options.watermark)
            changed = True
        if changed:
            xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            package.parts[name] = fill(xml.decode("utf-8"), values, extra).encode("utf-8")


def _watermark(header: Any, text: str) -> None:
    """A diagonal text shape behind the page, as Word's own watermark (VML), in a header."""
    p = etree.SubElement(header, w("p"))
    r = etree.SubElement(p, w("r"))
    pict = etree.SubElement(r, w("pict"))
    shape = etree.SubElement(pict, f"{{{VML}}}shape", nsmap={"v": VML, "o": OFFICE})
    shape.set("id", "MaestroWatermark")
    shape.set(f"{{{OFFICE}}}spid", "_x0000_s4097")
    shape.set("type", "#_x0000_t136")
    shape.set("style", "position:absolute;margin-left:0;margin-top:0;width:468pt;height:117pt;"
                       "rotation:315;z-index:-251654144;mso-position-horizontal:center;"
                       "mso-position-horizontal-relative:margin;mso-position-vertical:center;"
                       "mso-position-vertical-relative:margin")  # fmt: skip
    shape.set(f"{{{OFFICE}}}allowincell", "f")
    shape.set("fillcolor", "silver")
    shape.set("stroked", "f")
    etree.SubElement(shape, f"{{{VML}}}fill", opacity=".5")
    path = etree.SubElement(shape, f"{{{VML}}}textpath")
    path.set("style", 'font-family:"Calibri";font-size:1pt')
    path.set("string", text)


def _properties(package: _Package, options: Options) -> None:
    """Author, title and company: TUU and the document, never the people of the template."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    name = "docProps/core.xml"
    if name in package.zip.namelist():
        root = etree.fromstring(package.zip.read(name))
        values = {f"{{{DC}}}creator": COMPANY, f"{{{CP}}}lastModifiedBy": COMPANY,
                  f"{{{DC}}}title": options.title or "", f"{{{DC}}}subject": options.subject or "",
                  f"{{{DC}}}description": "", f"{{{CP}}}keywords": "",
                  f"{{{CP}}}revision": "1", f"{{{DCTERMS}}}created": now,
                  f"{{{DCTERMS}}}modified": now}  # fmt: skip
        for tag, value in values.items():
            el = root.find(tag)
            if el is None:
                el = etree.SubElement(root, tag)
            el.text = value
        for el in root.findall(f"{{{CP}}}lastPrinted"):
            root.remove(el)
        package.parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                             standalone=True)  # fmt: skip
    name = "docProps/app.xml"
    if name in package.zip.namelist():
        root = etree.fromstring(package.zip.read(name))
        company = root.find(f"{{{EXT}}}Company")
        if company is None:
            company = etree.SubElement(root, f"{{{EXT}}}Company")
        company.text = COMPANY
        package.parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                             standalone=True)  # fmt: skip


def _unique_drawing_ids(document_xml: bytes) -> bytes:
    """Ids that must not repeat, and fragments of two projects may share: wp:docPr and bookmarks.
    Only a repeated id changes (the first keeps its own, so fixed blocks stay as they were); a
    w:bookmarkEnd follows its w:bookmarkStart."""
    root = etree.fromstring(document_xml)
    drawings = list(root.iter(f"{{{WP}}}docPr"))
    taken = {el.get("id") for el in drawings}
    seen: set[str | None] = set()
    next_id = max((int(i) for i in taken if i and i.isdigit()), default=0) + 1
    for el in drawings:
        if el.get("id") in seen:
            el.set("id", str(next_id))
            next_id += 1
        seen.add(el.get("id"))
    starts = [el.get(w("id")) for el in root.iter(w("bookmarkStart"))]
    next_mark = max((int(i) for i in starts if i and i.isdigit()), default=0) + 1
    used: set[str | None] = set()
    open_ids: dict[str | None, str] = {}
    for el in root.iter(w("bookmarkStart"), w("bookmarkEnd")):
        old = el.get(w("id"))
        if el.tag == w("bookmarkStart"):
            new = old if old not in used else str(next_mark)
            if new != old:
                next_mark += 1
                el.set(w("id"), new or "")
            used.add(new)
            open_ids[old] = new or ""
        elif old in open_ids:
            el.set(w("id"), open_ids.pop(old))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _update_fields(package: _Package) -> None:
    name = "word/settings.xml"
    if name not in package.zip.namelist():
        return
    root = etree.fromstring(package.zip.read(name))
    if root.find(w("updateFields")) is None:
        el = etree.SubElement(root, w("updateFields"))
        el.set(w("val"), "true")
    package.parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                         standalone=True)  # fmt: skip


def draft_docx(db: Session, store: ObjectStore, document: Document, values: ValueSource,
               options: Options | None = None) -> bytes:  # fmt: skip
    options = options or Options()
    template = db.get(SourceDocument, document.template_id) if document.template_id else None
    if template is None:
        raise ValueError("Sem documento modelo para o rascunho (make seed-library).")
    package = _Package(store.get(template.package_key))
    fragments: list[str] = []
    for section in document.sections:
        if not section.active:
            continue
        block = db.get(TemplateBlock, section.block_id) if section.block_id else None
        if block is None:
            continue
        version = next(v for v in section.versions if v.number == section.current_version)
        first = next((v for v in section.versions if v.number == 1), version)
        nodes = version.content.get("content") or []
        now, assembled = by_entry(nodes), by_entry(first.content.get("content") or [])
        for i, entry in enumerate(block.body_template):
            if omitted(entry):
                continue
            if entry["mode"] != "adaptive" and entry.get("ooxml"):
                if now.get(i, []) == assembled.get(i, []):  # as assembled: the original OOXML
                    fragment = entry["ooxml"]
                    if entry["project"] != template.project_code:
                        fragment = _remap(package, store, fragment,
                                          block.ooxml_rels.get(entry["project"], {}))  # fmt: skip
                    fragments.append(fill(fragment, values))
                    continue
                ppr = _source_ppr(db, package, block, entry)  # changed by hand: as text
                for node in now.get(i, []):
                    fragments += [_paragraph(line, ppr) for line in _lines(node, values)]
                continue
            ppr = _source_ppr(db, package, block, entry)
            for node in nodes:
                if node.get("attrs", {}).get("entry") == i and node["type"] == "paragraph":
                    fragments.append(_paragraph(_text_of(node, values), ppr))
    body = rebuild(package.data, fragments)
    _headers(package, template, db, values, options)
    _update_fields(package)
    _properties(package, options)
    document_xml = _unique_drawing_ids(zipfile.ZipFile(io.BytesIO(body)).read(DOCUMENT))
    return package.write(document_xml)
