"""Processors per file kind: read the file, then merge the result into the ficha-base."""

from sqlalchemy.orm import Session

from app.ingest import (
    bom,
    circuit_sheet,
    consolidate,
    drawings,
    ficha_eletrotecnica,
    tabela_calculo,
    written,
)
from app.ingest.pipeline import register
from app.models import ProjectFile


@register("ficha_eletrotecnica")
def ficha(db: Session, file: ProjectFile, data: bytes) -> str:
    result = ficha_eletrotecnica.read(data)
    file.template_version = result.template_version
    return consolidate.apply(db, file, result)


@register("calc_summary")
def tabela(db: Session, file: ProjectFile, data: bytes) -> str:
    result = tabela_calculo.read(data)
    revision = consolidate.draft_revision(db, file.project_id, None)
    kept = circuit_sheet.manual_links(revision)  # circuits are replaced: keep what people linked
    summary = consolidate.apply(db, file, result)
    circuit_sheet.restore_manual_links(db, revision, kept)
    opened = circuit_sheet.link_and_compare(db, revision)
    if opened:
        summary += f" · {opened} conflito{'s' if opened > 1 else ''} com as 09-Folhas"
    return summary


@register("calc_circuit")
def folha09(db: Session, file: ProjectFile, data: bytes) -> str:
    reading = circuit_sheet.read(data, file.filename)
    file.template_version = reading.template
    return circuit_sheet.add_reading(db, file, reading)


@register("mqt")
@register("lpu")
def quantities(db: Session, file: ProjectFile, data: bytes) -> str:
    reading = bom.read(data)
    file.kind = reading.variant  # the title decides; detection and reader agree
    return bom.add_reading(db, file, reading)


@register("drawing_pdf")
def drawings_pdf(db: Session, file: ProjectFile, data: bytes) -> str:
    reading = drawings.read(data)
    result = reading.result
    result.warnings = reading.warnings
    summary = consolidate.apply(db, file, result)
    listed = f"índice com {len(reading.index)} folhas" if reading.index else "sem índice"
    return f"{reading.pages} páginas · {listed} · {summary}"


@register("mdj_docx")
@register("cte_docx")
def written_piece(db: Session, file: ProjectFile, data: bytes) -> str:
    return written.add_existing(db, file, data)


@register("identificacao_docx")
@register("termo_docx")
def form(db: Session, file: ProjectFile, data: bytes) -> str:
    name = "Identificação" if file.kind == "identificacao_docx" else "Termo de responsabilidade"
    return f"{name} existente: é lido na validação (não entra na ficha-base)"
