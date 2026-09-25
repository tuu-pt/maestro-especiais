"""Processors per file kind: read the file, then merge the result into the ficha-base."""

from sqlalchemy.orm import Session

from app.ingest import bom, circuit_sheet, consolidate, ficha_eletrotecnica, tabela_calculo
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
