"""Automatic fidelity checks of what is exported (Phase 6): an empty list of problems means it
opens in Word and Excel without a repair (as far as a machine can tell; the rest is in
docs/fase6-verificacao-manual.md).

.docx: the package (content types, relationships, unique ids), python-docx opens it, no
placeholder nor internal mark left, every style used exists, as many images, formulas and tables
as the source sections, and LibreOffice converts it (when it is installed).
.xlsm: every part except the edited sheet is the template's, byte for byte (vbaProject.bin and
the data validations included), and the Phase 1 reader reads the ficha-base back.
"""

import io
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import docx
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PKG_R = "http://schemas.openxmlformats.org/package/2006/relationships"
PLACEHOLDER = "{{v:"
MISSING = "[falta:"
# what only the editor knows: nothing of it may reach a file
INTERNAL = ("data-value", "data-generated", "data-citation", '"type": "locked"', '"marks":')


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # checks that could not run here

    @property
    def ok(self) -> bool:
        return not self.problems


def _parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}


def package_problems(parts: dict[str, bytes]) -> list[str]:
    """Content types for every part and every internal relationship pointing to a part."""
    problems = []
    types = etree.fromstring(parts["[Content_Types].xml"])
    overrides = {o.get("PartName", "").lstrip("/") for o in types.iter(f"{{{CT}}}Override")}
    defaults = {d.get("Extension", "").lower() for d in types.iter(f"{{{CT}}}Default")}
    for name in parts:
        if name == "[Content_Types].xml":
            continue
        if name not in overrides and name.rsplit(".", 1)[-1].lower() not in defaults:
            problems.append(f"Parte sem tipo de conteúdo: {name}")
    for name, blob in parts.items():
        if not name.endswith(".rels"):
            continue
        base = posixpath.dirname(posixpath.dirname(name))  # word/_rels/x.rels → word
        for rel in etree.fromstring(blob).iter(f"{{{PKG_R}}}Relationship"):
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(
                posixpath.join(base, target))  # fmt: skip
            if path not in parts:
                problems.append(f"Relação para uma parte inexistente: {name} → {target}")
    return problems


def _styles(parts: dict[str, bytes]) -> set[str]:
    root = etree.fromstring(parts["word/styles.xml"])
    return {s.get(f"{{{W}}}styleId", "") for s in root.iter(f"{{{W}}}style")}


def _xml_parts(parts: dict[str, bytes]) -> dict[str, bytes]:
    return {n: b for n, b in parts.items()
            if re.fullmatch(r"word/(document|header\d*|footer\d*)\.xml", n)}  # fmt: skip


def check_docx(data: bytes, *, expected: Counter[str] | None = None, official: bool = True,
               watermark: str | None = None, libreoffice: bool = True) -> Report:  # fmt: skip
    report = Report()
    try:
        parts = _parts(data)
    except zipfile.BadZipFile:
        report.problems.append("O ficheiro não é um pacote OOXML (zip).")
        return report
    report.problems += package_problems(parts)
    xml = _xml_parts(parts)
    styles = _styles(parts)
    for name, blob in xml.items():
        text = blob.decode("utf-8", "replace")
        if PLACEHOLDER in text:
            report.problems.append(f"Ficou um marcador {{{{v:…}}}} em {name}.")
        if official and MISSING in text:
            report.problems.append(f"Ficou um valor em falta em {name}.")
        if any(mark in text for mark in INTERNAL):
            report.problems.append(f"Ficou uma marca interna do editor em {name}.")
        root = etree.fromstring(blob)
        ids = [el.get("id") for el in root.iter(f"{{{WP}}}docPr")]
        if len(ids) != len(set(ids)):
            report.problems.append(f"IDs de imagem repetidos em {name}.")
        bookmarks = [el.get(f"{{{W}}}id") for el in root.iter(f"{{{W}}}bookmarkStart")]
        if len(bookmarks) != len(set(bookmarks)):
            report.problems.append(f"IDs de marcadores repetidos em {name}.")
        for tag in ("pStyle", "rStyle", "tblStyle"):
            for el in root.iter(f"{{{W}}}{tag}"):
                if el.get(f"{{{W}}}val") not in styles:
                    report.problems.append(f"Estilo inexistente no modelo: {el.get(f'{{{W}}}val')}")
    headers = "".join(b.decode("utf-8", "replace") for n, b in xml.items() if "header" in n)
    if watermark and watermark not in headers:
        report.problems.append("Falta a marca de água nos cabeçalhos.")
    if not watermark and "RASCUNHO" in headers:
        report.problems.append("Marca de água de rascunho numa peça oficial.")
    if expected is not None:
        from app.export.docx import ooxml_counts

        found = ooxml_counts(parts["word/document.xml"].decode("utf-8"))
        for what in ("images", "formulas", "tables"):
            if found[what] != expected[what]:
                report.problems.append(f"{what}: {found[what]} no ficheiro, {expected[what]} nas "
                                       "secções de origem.")  # fmt: skip
    try:
        docx.Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - any failure to open is the problem itself
        report.problems.append(f"O python-docx não abre o ficheiro ({type(exc).__name__}).")
    if libreoffice:
        problem, note = convert_with_libreoffice(data, "docx")
        report.problems += [problem] if problem else []
        report.notes += [note] if note else []
    report.problems = list(dict.fromkeys(report.problems))
    return report


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_with_libreoffice(data: bytes, ext: str, *, timeout_s: int = 180
                             ) -> tuple[str | None, str | None]:  # fmt: skip
    """(problem, note): LibreOffice in headless mode turns the file into a PDF."""
    pdf, problem = to_pdf(data, ext, timeout_s=timeout_s)
    if pdf is None and problem is None:
        return None, "LibreOffice não está instalado aqui: conversão não verificada."
    return problem, None


def to_pdf(data: bytes, ext: str, *, timeout_s: int = 180) -> tuple[bytes | None, str | None]:
    """(pdf, problem); (None, None) when LibreOffice is not installed."""
    binary = soffice()
    if binary is None:
        return None, None
    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, f"peca.{ext}")
        with open(source, "wb") as f:
            f.write(data)
        env = {**os.environ, "HOME": tmp}  # its own profile: no lock between processes
        try:
            done = subprocess.run(
                [binary, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", tmp,
                 source], capture_output=True, timeout=timeout_s, env=env, check=False,
            )  # fmt: skip
        except subprocess.TimeoutExpired:
            return None, "O LibreOffice não converteu o ficheiro a tempo."
        target = os.path.join(tmp, "peca.pdf")
        if done.returncode != 0 or not os.path.exists(target) or os.path.getsize(target) == 0:
            return None, f"O LibreOffice não converteu o ficheiro (código {done.returncode})."
        with open(target, "rb") as f:
            return f.read(), None


def check_xlsm(data: bytes, template: bytes, *, sheet: str, reread: dict[str, Any] | None = None,
               libreoffice: bool = False) -> Report:  # fmt: skip
    """Every part except `sheet` byte for byte the template's, and the data validations too."""
    report = Report()
    out, tpl = _parts(data), _parts(template)
    if list(out) != list(tpl):
        report.problems.append("As partes do pacote mudaram (nomes ou ordem).")
    for name, blob in tpl.items():
        if name != sheet and out.get(name) != blob:
            report.problems.append(f"Parte alterada: {name}")
    for tag in ("dataValidations", "extLst"):
        before = _subtree(tpl[sheet], tag)
        after = _subtree(out.get(sheet, b""), tag)
        if before != after:
            report.problems.append(f"As validações de dados mudaram ({tag}).")
    if reread is not None:
        from app.ingest import ficha_eletrotecnica

        read = {c.key: c.value for c in ficha_eletrotecnica.read(data).values}
        for key, value in reread.items():
            if read.get(key) != value:
                report.problems.append(f"Releitura da ficha: {key} não coincide.")
    if libreoffice:
        problem, note = convert_with_libreoffice(data, "xlsm")
        report.problems += [problem] if problem else []
        report.notes += [note] if note else []
    return report


def _subtree(xml: bytes, tag: str) -> bytes | None:
    """The canonical form (C14N) of the first element called `tag` of a sheet."""
    if not xml:
        return None
    root = etree.fromstring(xml)
    el = next((e for e in root.iter() if etree.QName(e).localname == tag), None)
    return None if el is None else etree.tostring(el, method="c14n")
