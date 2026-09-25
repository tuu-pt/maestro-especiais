"""Knowledge base (SPEC 7.5, screen G): cable dictionary and typology lexicon.

Everyone reads it; only a curator approves or rejects, and every decision is audited.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit import record
from app.auth import CurrentUser, User, require_role
from app.db import get_session
from app.models import CableDesignation, CableEquivalence, Typology, TypologyTerm

router = APIRouter(prefix="/knowledge", tags=["base de conhecimento"])

DB = Annotated[Session, Depends(get_session)]
Curador = Annotated[User, Depends(require_role("curador"))]
Reviewed = CableDesignation | CableEquivalence | Typology | TypologyTerm


class Review(BaseModel):
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class OccurrenceOut(BaseModel):
    project_code: str
    source: str
    source_file: str
    locator: str
    raw_text: str
    geometry: str | None


class DesignationOut(Review):
    id: uuid.UUID
    canonical: str
    aliases: list[str]
    kind: str
    flexible: bool | None
    occurrences: list[OccurrenceOut]


class EquivalenceOut(Review):
    id: uuid.UUID
    a: str
    b: str
    reason: str
    evidence: list[dict[str, Any]]


class CablesOut(BaseModel):
    designations: list[DesignationOut]
    equivalences: list[EquivalenceOut]


class TermOut(Review):
    id: uuid.UUID
    term: str
    relation: str
    evidence: list[dict[str, Any]]


class TypologyOut(Review):
    id: uuid.UUID
    name: str
    evidence: list[dict[str, Any]]
    terms: list[TermOut]


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


def _review(row: Reviewed) -> dict[str, Any]:
    return {
        "status": row.status, "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at, "review_note": row.review_note,
    }  # fmt: skip


@router.get("/cables")
def cables(db: DB, _: CurrentUser) -> CablesOut:
    designations = db.scalars(
        select(CableDesignation)
        .options(selectinload(CableDesignation.occurrences))
        .order_by(CableDesignation.canonical)
    ).all()
    names = {d.id: d.canonical for d in designations}
    equivalences = db.scalars(select(CableEquivalence).order_by(CableEquivalence.created_at)).all()
    return CablesOut(
        designations=[
            DesignationOut(
                id=d.id, canonical=d.canonical, aliases=d.aliases, kind=d.kind,
                flexible=d.flexible, **_review(d),
                occurrences=[OccurrenceOut.model_validate(o, from_attributes=True)
                             for o in d.occurrences],
            )
            for d in designations
        ],
        equivalences=[
            EquivalenceOut(id=e.id, a=names[e.a_id], b=names[e.b_id], reason=e.reason,
                           evidence=e.evidence, **_review(e))
            for e in equivalences
        ],
    )  # fmt: skip


@router.get("/typologies")
def typologies(db: DB, _: CurrentUser) -> list[TypologyOut]:
    rows = db.scalars(
        select(Typology).options(selectinload(Typology.terms)).order_by(Typology.name)
    ).all()
    return [
        TypologyOut(
            id=t.id, name=t.name, evidence=t.evidence, **_review(t),
            terms=[TermOut(id=x.id, term=x.term, relation=x.relation, evidence=x.evidence,
                           **_review(x)) for x in t.terms],
        )
        for t in rows
    ]  # fmt: skip


Kind = Literal["cable-designations", "cable-equivalences", "typologies", "typology-terms"]
MODELS: dict[str, type[Reviewed]] = {
    "cable-designations": CableDesignation,
    "cable-equivalences": CableEquivalence,
    "typologies": Typology,
    "typology-terms": TypologyTerm,
}


def _label(row: Reviewed) -> str:
    """What the decision was about, for the audit sentence. Never personal data."""
    if isinstance(row, CableDesignation):
        return row.canonical
    if isinstance(row, CableEquivalence):
        return f"{row.a.canonical} ≈ {row.b.canonical}"
    if isinstance(row, Typology):
        return row.name
    return f"{row.term} ({row.typology.name})"


def _sync_aliases(row: CableEquivalence) -> None:
    """An approved equivalence makes each family an alias of the other; rejecting undoes it."""
    for mine, other in ((row.a, row.b), (row.b, row.a)):
        aliases = [x for x in mine.aliases if x != other.canonical]
        if row.status == "approved":
            aliases.append(other.canonical)
        mine.aliases = sorted(aliases)


@router.post("/{kind}/{item_id}/review")
def review(kind: Kind, item_id: uuid.UUID, body: DecisionIn, db: DB, user: Curador) -> Review:
    row = cast("Reviewed | None", db.get(MODELS[kind], item_id))
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Elemento da base de conhecimento não encontrado."
        )
    before = row.status
    row.status = body.decision
    row.reviewed_by, row.reviewed_at = user.id, datetime.now(UTC)
    row.review_note = (body.note or "").strip() or None
    if isinstance(row, CableEquivalence):
        _sync_aliases(row)
    record(
        db, user, f"knowledge.{body.decision}", type(row).__tablename__, row.id,
        {"kind": kind, "label": _label(row), "from": before}, project_id=None,
    )  # fmt: skip
    db.commit()
    return Review(**_review(row))
