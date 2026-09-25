"""Split an MDJ or CTE (.docx) into its sections, keeping the original OOXML (SPEC 8.3, Phase 3).

The reference documents follow one skeleton:

- the cover: every body element before the table of contents;
- the table of contents: a 1x2 table whose text starts with "Conteúdo" (or holds a TOC field);
- level 1: a 1-row, 2-cell table with the title (the number comes from Word's numbering);
- level 2: a paragraph whose style is "heading 2" (style id "Ttulo2" in the Portuguese Word);
- the signature: from "<Local>, <mês> de <ano>" or "O Técnico" to the end, after the last level 1.

Nothing is re-serialized through python-docx: each section keeps its body elements as they are
(`ooxml`, one fragment per section) with the relationships it uses (`rels`). The package is the
document with an empty body (only the final sectPr): styles, numbering, theme, settings, headers
and footers stay there, once per source document. `rebuild(package, fragments)` gives the same
document back (the round-trip test compares document.xml canonically and every other part byte
for byte).
"""

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from app.ingest.detect import fold

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_R = "http://schemas.openxmlformats.org/package/2006/relationships"
DOCUMENT = "word/document.xml"
DOCUMENT_RELS = "word/_rels/document.xml.rels"
STYLES = "word/styles.xml"


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


_SIGNATURE = re.compile(r"^[^\W\d][\w .'-]*,\s+[a-zç]+\s+de\s+\d{4}\.?$|^o\s+tecnico\b")


class DocxError(ValueError):
    """The file is not a Word document this splitter understands."""


@dataclass(frozen=True)
class Rel:
    """A relationship used by a section (image, hyperlink, header of a section break…)."""

    type: str  # last segment of the relationship type, e.g. "image", "hyperlink"
    target: str
    external: bool
    sha256: str | None = None  # of the part's bytes, for media stored by content


@dataclass
class Section:
    order: int
    kind: str  # cover | index | block | signature
    level: int  # 1 or 2 for blocks; 0 for cover, index and signature
    title: str
    key: str  # e.g. "introducao", "dimensionamento_eletrico.quedas_de_tensao"
    elements: list[Any] = field(repr=False)
    rels: dict[str, Rel] = field(default_factory=dict)

    @property
    def ooxml(self) -> str:
        return "".join(etree.tostring(e, encoding="unicode") for e in self.elements)

    @property
    def text(self) -> str:
        """Plain text, one line per paragraph (table cells included), empty lines dropped."""
        lines = []
        for e in self.elements:
            for p in e.iter(w("p")):
                line = "".join(t.text or "" for t in p.iter(w("t")))
                if line.strip():
                    lines.append(line)
        return "\n".join(lines)

    def stats(self) -> dict[str, int]:
        def count(tag: str) -> int:
            return sum(1 for e in self.elements for _ in e.iter(tag))

        return {
            "elements": len(self.elements),
            "paragraphs": count(w("p")),
            "tables": count(w("tbl")),
            "images": count(w("drawing")) + count("{urn:schemas-microsoft-com:vml}imagedata"),
            "fields": count(w("instrText")) + count(w("fldSimple")),
        }


@dataclass
class SplitDocument:
    sha256: str
    package: bytes  # the .docx with an empty body (only the final sectPr)
    sections: list[Section]
    media: dict[str, bytes]  # sha256 -> bytes of every part a section refers to
    warnings: list[str]


# ---------------------------------------------------------------- helpers


def _text(e: Any) -> str:
    return "".join(t.text or "" for t in e.iter(w("t")))


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(":").strip()


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", fold(title)).strip("_") or "sem_titulo"


def _heading2_styles(z: zipfile.ZipFile) -> set[str]:
    """Style ids whose name is "heading 2" (the id is localized: "Ttulo2" in Portuguese)."""
    if STYLES not in z.namelist():
        return set()
    root = etree.fromstring(z.read(STYLES))
    ids = set()
    for style in root.iter(w("style")):
        name = style.find(w("name"))
        if name is not None and (name.get(w("val")) or "").lower() == "heading 2":
            ids.add(style.get(w("styleId")) or "")
    return ids


def _is_toc(e: Any) -> bool:
    instr = " ".join(i.text or "" for i in e.iter(w("instrText")))
    return bool(re.search(r"\bTOC\b", instr)) or fold(_text(e)).startswith("conteudo")


def _band_title(e: Any) -> str | None:
    """Title of a level-1 band: a table with one row and two cells, with text."""
    if e.tag != w("tbl"):
        return None
    rows = e.findall(w("tr"))
    if len(rows) != 1 or len(rows[0].findall(w("tc"))) != 2:
        return None
    title = _clean_title(_text(e))
    return title or None


def _heading2_title(e: Any, styles: set[str]) -> str | None:
    if e.tag != w("p"):
        return None
    style = e.find(f"{w('pPr')}/{w('pStyle')}")
    if style is None or style.get(w("val")) not in styles:
        return None
    return _clean_title(_text(e)) or None


def _rel_ids(elements: list[Any]) -> set[str]:
    ids: set[str] = set()
    for e in elements:
        for node in e.iter():
            for name, value in node.attrib.items():
                if name.startswith(f"{{{R}}}"):
                    ids.add(value)
    return ids


# ---------------------------------------------------------------- split


def split(data: bytes) -> SplitDocument:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        root = etree.fromstring(z.read(DOCUMENT))
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError) as exc:
        raise DocxError("Não é um documento Word (.docx) legível.") from exc
    body = root.find(w("body"))
    if body is None:
        raise DocxError("O documento não tem corpo.")
    children = list(body)
    final_sect = children[-1] if children and children[-1].tag == w("sectPr") else None
    content = children[:-1] if final_sect is not None else children
    styles = _heading2_styles(z)
    warnings: list[str] = []

    toc = next((i for i, e in enumerate(content) if e.tag == w("tbl") and _is_toc(e)), None)
    if toc is None:
        warnings.append("Sem índice (Conteúdo): a capa não foi separada.")

    sections: list[Section] = []
    current: Section | None = None
    parent_key = ""
    seen: dict[str, int] = {}

    def start(kind: str, level: int, title: str, key: str) -> Section:
        n = seen.get(key, 0) + 1
        seen[key] = n
        section = Section(
            len(sections) + 1, kind, level, title, key if n == 1 else f"{key}_{n}", []
        )
        sections.append(section)
        return section

    for i, e in enumerate(content):
        if toc is not None and i < toc:
            current = current or start("cover", 0, "Capa", "capa")
        elif i == toc:
            current = start("index", 0, "Índice", "indice")
        elif (band := _band_title(e)) is not None:
            parent_key = slug(band)
            current = start("block", 1, band, parent_key)
        elif (heading := _heading2_title(e, styles)) is not None:
            if not parent_key:
                warnings.append(
                    f"Título de nível 2 «{heading}» antes de qualquer faixa de nível 1."
                )
            key = f"{parent_key}.{slug(heading)}" if parent_key else slug(heading)
            current = start("block", 2, heading, key)
        elif current is None:
            current = start("block", 1, "Sem título", "sem_titulo")
            warnings.append("Conteúdo antes da primeira faixa de nível 1.")
        current.elements.append(e)

    _split_signature(sections)
    rels = _relationships(z)
    media: dict[str, bytes] = {}
    for section in sections:
        for rid in sorted(_rel_ids(section.elements)):
            rel = rels.get(rid)
            if rel is None:
                warnings.append(f"Relação {rid} sem destino em {section.title}.")
                continue
            if not rel.external:
                part = _part_name(rel.target)
                if part in z.namelist():
                    blob = z.read(part)
                    digest = hashlib.sha256(blob).hexdigest()
                    media[digest] = blob
                    rel = Rel(rel.type, rel.target, rel.external, digest)
            section.rels[rid] = rel

    for e in content:
        body.remove(e)
    return SplitDocument(
        sha256=hashlib.sha256(data).hexdigest(),
        package=_replace_document(z, root),
        sections=sections,
        media=media,
        warnings=warnings,
    )


def _split_signature(sections: list[Section]) -> None:
    """Move "<Local>, <mês> de <ano>" / "O Técnico" and what follows into its own section.

    It is at the end of the last section (dúvidas e casos omissos, a level-1 band).
    """
    tail = sections[-1] if sections and sections[-1].kind == "block" else None
    if tail is None:
        return
    for i, e in enumerate(tail.elements[1:], start=1):
        if e.tag == w("p") and _SIGNATURE.match(fold(_text(e)).strip()):
            title = "Local, data e técnico"
            signature = Section(
                tail.order + 1, "signature", 0, title, "assinatura", tail.elements[i:]
            )
            tail.elements = tail.elements[:i]
            sections.append(signature)
            return


def _relationships(z: zipfile.ZipFile) -> dict[str, Rel]:
    if DOCUMENT_RELS not in z.namelist():
        return {}
    rels = {}
    for rel in etree.fromstring(z.read(DOCUMENT_RELS)).iter(f"{{{PKG_R}}}Relationship"):
        rels[rel.get("Id") or ""] = Rel(
            type=(rel.get("Type") or "").rsplit("/", 1)[-1],
            target=rel.get("Target") or "",
            external=rel.get("TargetMode") == "External",
        )
    return rels


def _part_name(target: str) -> str:
    """Part name of a target relative to word/ ("media/a.png" -> "word/media/a.png")."""
    if target.startswith("/"):
        return target.lstrip("/")
    parts: list[str] = ["word"]
    for piece in target.split("/"):
        if piece == "..":
            if parts:
                parts.pop()
        elif piece and piece != ".":
            parts.append(piece)
    return "/".join(parts)


def _replace_document(z: zipfile.ZipFile, root: Any) -> bytes:
    """The same package with document.xml replaced (every other part copied byte for byte)."""
    out = io.BytesIO()
    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in z.infolist():
            dst.writestr(info, xml if info.filename == DOCUMENT else z.read(info.filename))
    return out.getvalue()


# ---------------------------------------------------------------- rebuild


def rebuild(package: bytes, fragments: list[str]) -> bytes:
    """Put section fragments back into the package, before the final sectPr, in the given order."""
    z = zipfile.ZipFile(io.BytesIO(package))
    root = etree.fromstring(z.read(DOCUMENT))
    body = root.find(w("body"))
    if body is None:
        raise DocxError("O pacote não tem corpo.")
    sect = body.find(w("sectPr"))
    wrapper_open = "<wrap " + " ".join(
        f'xmlns:{p}="{u}"' if p else f'xmlns="{u}"' for p, u in root.nsmap.items()
    ) + ">"  # fmt: skip
    for fragment in fragments:
        for e in etree.fromstring(wrapper_open + fragment + "</wrap>"):
            if sect is not None:
                sect.addprevious(e)
            else:
                body.append(e)
    return _replace_document(z, root)


def canonical_document(data: bytes) -> bytes:
    """document.xml in canonical form (C14N), to compare two documents."""
    root = etree.fromstring(zipfile.ZipFile(io.BytesIO(data)).read(DOCUMENT))
    return etree.tostring(root, method="c14n")
