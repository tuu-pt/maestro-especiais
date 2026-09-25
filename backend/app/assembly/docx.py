"""Draft .docx of an assembled document (Phase 4; the official export is Phase 6).

Built on the package of the template document (styles, numbering, theme, headers) [A CONFIRMAR]:
- fixed paragraphs: the block's original OOXML;
- parametric: the same OOXML, each {{v:key}} replaced in the w:t it is in (the run keeps its
  formatting); missing values are written as "[falta: …]";
- adaptive: the current version's paragraphs, with the paragraph properties of the source text;
- fragments of another reference project: their relationships are copied into the package
  (media from S3, new relationship ids);
- headers and footers: the template project's technician and date become placeholders too;
- Word updates the fields (the index) when the file is opened.
Inactive sections are left out. Personal values are only written here, in the backend.
"""

import io
import re
import zipfile
from html import escape
from typing import Any

from lxml import etree
from sqlalchemy.orm import Session

from app.assembly.assemble import PLACEHOLDER
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


def _value_text(values: ValueSource, key: str) -> str:
    r = values.resolve(key)
    return f"[falta: {label(key)}]" if r.missing else (r.text or "")


def fill(ooxml: str, values: ValueSource) -> str:
    """Write the values of the placeholders into an OOXML fragment (inside its w:t)."""
    return PLACEHOLDER.sub(lambda m: escape(_value_text(values, m.group(1)), quote=False), ooxml)


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
        if ext in MEDIA_TYPES and not any(
            d.get("Extension", "").lower() == ext for d in self.types.iter(f"{{{CT}}}Default")
        ):
            etree.SubElement(self.types, f"{{{CT}}}Default", Extension=ext,
                             ContentType=MEDIA_TYPES[ext])  # fmt: skip
        self._copied[sha] = rid
        return rid

    def write(self, document_xml: bytes) -> bytes:
        self.parts[DOCUMENT] = document_xml
        self.parts[DOCUMENT_RELS] = etree.tostring(self.rels, xml_declaration=True,
                                                   encoding="UTF-8", standalone=True)  # fmt: skip
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
    out = []
    for child in node.get("content") or []:
        mark = next((m for m in child.get("marks") or [] if m["type"] == "value"), None)
        if mark is not None:
            out.append(_value_text(values, mark["attrs"]["key"]))
        else:
            out.append(child.get("text", ""))
    return "".join(out)


def _headers(package: _Package, template: SourceDocument, db: Session, values: ValueSource) -> None:
    """Technician and date of the template project in headers and footers become the target's."""
    signature = next((s for s in template.sections if s.kind == "signature"), None)
    facts: list[Fact] = signature_facts(signature.text.splitlines()) if signature else []
    facts = [f for f in facts if f.key == "tec.nome"]
    date = Fact("doc.data", "mês de ano", _MONTH_YEAR)
    upper = [text_fact(f.key, f.value.upper()) for f in facts]
    facts += [f for f in upper if f] + [date]
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
        if changed:
            xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            package.parts[name] = fill(xml.decode("utf-8"), values).encode("utf-8")


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


def draft_docx(db: Session, store: ObjectStore, document: Document, values: ValueSource) -> bytes:
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
        nodes = version.content.get("content") or []
        for i, entry in enumerate(block.body_template):
            if entry["mode"] != "adaptive" and entry.get("ooxml"):
                fragment = entry["ooxml"]
                if entry["project"] != template.project_code:
                    fragment = _remap(package, store, fragment,
                                      block.ooxml_rels.get(entry["project"], {}))  # fmt: skip
                fragments.append(fill(fragment, values))
                continue
            ppr = _source_ppr(db, package, block, entry)
            for node in nodes:
                if node.get("attrs", {}).get("entry") == i and node["type"] == "paragraph":
                    fragments.append(_paragraph(_text_of(node, values), ppr))
    body = rebuild(package.data, fragments)
    _headers(package, template, db, values)
    _update_fields(package)
    document_xml = zipfile.ZipFile(io.BytesIO(body)).read(DOCUMENT)
    return package.write(document_xml)
