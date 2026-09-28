"""What the rules of one validation run can read (Phase 5)."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BomItem,
    CableDesignation,
    CableEquivalence,
    Circuit,
    FichaRevision,
    FichaValue,
    Project,
    RegulationDoc,
    Typology,
)
from app.validation.pieces import Fact, Paragraph, Piece, PieceData, SectionInfo


@dataclass
class Context:
    db: Session
    project: Project
    revision: FichaRevision
    pieces: dict[str, Piece]
    data: dict[str, PieceData]
    ficha: dict[str, FichaValue] = field(default_factory=dict)
    circuits: list[Circuit] = field(default_factory=list)
    bom: list[BomItem] = field(default_factory=list)

    @classmethod
    def load(cls, db: Session, project: Project, revision: FichaRevision,
             pieces: dict[str, Piece], data: dict[str, PieceData]) -> "Context":  # fmt: skip
        ficha = {v.key: v for v in revision.values}
        circuits = list(revision.circuits)
        bom = list(revision.bom_items)
        return cls(db, project, revision, pieces, data, ficha, circuits, bom)

    # ------------------------------------------------------------ pieces and facts

    @property
    def ficha_date(self) -> str | None:
        at: datetime | None = self.revision.confirmed_at
        return at.date().isoformat() if at else None

    def ficha_value(self, key: str) -> Any:
        fv = self.ficha.get(key)
        return None if fv is None or fv.value in (None, "", []) else fv.value

    def of_kind(self, *kinds: str) -> list[Piece]:
        return [p for p in self.pieces.values() if p.kind in kinds]

    @cached_property
    def _facts_by_key(self) -> dict[str, list[Fact]]:
        out: dict[str, list[Fact]] = defaultdict(list)
        for ref, data in self.data.items():
            if ref in self.pieces:
                for f in data.facts:
                    out[f.key].append(f)
        return out

    def facts(self, key: str, *, comparable: bool | None = True) -> list[Fact]:
        found = self._facts_by_key.get(key, [])
        if comparable is None:
            return list(found)
        return [f for f in found if f.comparable == comparable]

    def facts_with_prefix(self, prefix: str) -> list[Fact]:
        return [f for k, fs in self._facts_by_key.items() if k.startswith(prefix) for f in fs]

    def paragraphs(self, *kinds: str) -> list[Paragraph]:
        refs = [r for r in self.data if r in self.pieces
                and (not kinds or self.pieces[r].kind in kinds)]  # fmt: skip
        return [p for r in refs for p in self.data[r].paragraphs]

    def sections(self, piece: Piece) -> list[SectionInfo]:
        return self.data[piece.ref].sections if piece.ref in self.data else []

    # ------------------------------------------------------------ knowledge (Phase 3)

    @cached_property
    def cables(self) -> list[CableDesignation]:
        return list(self.db.scalars(select(CableDesignation).order_by(CableDesignation.canonical)))

    @cached_property
    def cable_equivalences(self) -> list[CableEquivalence]:
        return list(self.db.scalars(select(CableEquivalence)))

    @cached_property
    def typologies(self) -> list[Typology]:
        return list(self.db.scalars(select(Typology).order_by(Typology.name)))

    @cached_property
    def regulations(self) -> list[RegulationDoc]:
        return list(self.db.scalars(select(RegulationDoc).order_by(RegulationDoc.code)))
