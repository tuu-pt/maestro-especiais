"""Processors per file kind: read the file, then merge the result into the ficha-base."""

from sqlalchemy.orm import Session

from app.ingest import consolidate, ficha_eletrotecnica, tabela_calculo
from app.ingest.pipeline import register
from app.models import ProjectFile


@register("ficha_eletrotecnica")
def ficha(db: Session, file: ProjectFile, data: bytes) -> str:
    result = ficha_eletrotecnica.read(data)
    file.template_version = result.template_version
    return consolidate.apply(db, file, result)


@register("calc_summary")
def tabela(db: Session, file: ProjectFile, data: bytes) -> str:
    return consolidate.apply(db, file, tabela_calculo.read(data))
