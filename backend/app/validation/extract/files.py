"""Pieces read from the project files (ficha eletrotécnica, Tabela, MQT/LPU, drawings)."""

from sqlalchemy.orm import Session

from app.models import FichaRevision, Project
from app.validation.pieces import Piece


def pieces(db: Session, project: Project, revision: FichaRevision) -> list[Piece | None]:
    return []
