"""Reader results → ficha-base (SPEC 8.1 step 2, P5, P1).

- A value read for the first time is added as pending.
- A newer file of the same source replaces that source's value.
- A different source that agrees adds nothing; one that disagrees opens a FichaConflict and the
  value stays empty until a person resolves it. Nothing is ever chosen by majority or date.
- A confirmed revision is never changed: the next reading starts revision B, C…
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ingest.base import ReadResult, to_number
from app.ingest.detect import fold
from app.ingest.keys import info
from app.models import (
    BomItem,
    Circuit,
    CircuitSheet,
    FichaConflict,
    FichaRevision,
    FichaValue,
    ProjectFile,
)


def latest_revision(db: Session, project_id: uuid.UUID) -> FichaRevision | None:
    return db.scalars(
        select(FichaRevision)
        .where(FichaRevision.project_id == project_id)
        .order_by(FichaRevision.created_at.desc(), FichaRevision.label.desc())
        .limit(1)
    ).first()


def open_conflict(value: FichaValue) -> FichaConflict | None:
    return next((c for c in value.conflicts if c.resolved_at is None), None)


def _next_label(label: str) -> str:
    return chr(ord(label[-1]) + 1) if label[-1] < "Z" else label + "A"


def draft_revision(db: Session, project_id: uuid.UUID, actor_id: str | None) -> FichaRevision:
    """The revision readings go into: the current draft, or a new one after a confirmation."""
    latest = latest_revision(db, project_id)
    if latest is not None and latest.status == "draft":
        return latest
    revision = FichaRevision(
        project_id=project_id,
        label=_next_label(latest.label) if latest else "A",
        created_by=actor_id,
    )
    db.add(revision)
    db.flush()
    if latest is not None:  # start from what was confirmed
        for v in latest.values:
            db.add(
                FichaValue(
                    revision_id=revision.id,
                    key=v.key, group=v.group, label_pt=v.label_pt, value=v.value, unit=v.unit,
                    personal_data=v.personal_data, status="pending", source_type=v.source_type,
                    source_ref=v.source_ref, source_file_id=v.source_file_id,
                )
            )  # fmt: skip
        new_ids: dict[str, str] = {}
        for c in latest.circuits:
            data = {k: getattr(c, k) for k in _CIRCUIT_FIELDS}
            copy = Circuit(id=uuid.uuid4(), revision_id=revision.id, **data)
            new_ids[str(c.id)] = str(copy.id)
            db.add(copy)
        for s in latest.circuit_sheets:
            db.add(
                CircuitSheet(
                    revision_id=revision.id, source_file_id=s.source_file_id,
                    origin_hint=s.origin_hint, destination_hint=s.destination_hint,
                    template=s.template, values=s.values,
                    circuit_ids=[new_ids[i] for i in s.circuit_ids if i in new_ids],
                    link_status=s.link_status, linked_by=s.linked_by, linked_at=s.linked_at,
                )
            )  # fmt: skip
        for b in latest.bom_items:
            db.add(BomItem(revision_id=revision.id, **{k: getattr(b, k) for k in _BOM_FIELDS}))
        db.flush()
        db.refresh(revision)
    return revision


_BOM_FIELDS = (
    "source_file_id", "variant", "row_index", "source_ref", "code", "level", "parent_code", "kind",
    "designation", "unit", "quantity", "unit_price", "total", "chapter_total", "link_key",
    "link_status", "link_rule", "linked_by", "linked_at",
)  # fmt: skip


_CIRCUIT_FIELDS = (
    "source_file_id", "row_index", "section", "origin", "destination", "kva", "voltage_v",
    "protection_type", "ib_a", "in_a", "idn_ma", "iz_a", "i2_a", "iz145_a", "cable_raw",
    "cable_normalized", "section_mm2", "length_m", "vd_section_pct", "vd_upstream_pct",
    "vd_total_pct", "breaking_capacity_ka", "pole_type", "installation", "phases", "insulation",
    "conductor", "ref_method", "rtiebt_table", "source_ref",
)  # fmt: skip


def comparable(key: str, value: Any) -> Any:
    """Form in which two sources are compared: numbers as numbers, text folded."""
    if value is None:
        return None
    if info(key).numeric:
        number = to_number(value)
        return number if number is not None else fold(value)
    if isinstance(value, list):
        return [fold(v) for v in value]
    text = fold(value)
    if key == "ele.entrada":
        return "trif" if text.startswith("tri") else ("mono" if text.startswith("mon") else text)
    return text


def _candidate(value: Any, result: ReadResult, ref: str, file: ProjectFile) -> dict[str, Any]:
    return {
        "value": value,
        "source_type": result.source_type,
        "source_ref": ref,
        "source_file_id": str(file.id),
        "file_date": (file.created_at or datetime.now(UTC)).isoformat(timespec="seconds"),
    }


def _as_candidate(v: FichaValue) -> dict[str, Any]:
    return {
        "value": v.value,
        "source_type": v.source_type,
        "source_ref": v.source_ref,
        "source_file_id": str(v.source_file_id) if v.source_file_id else None,
        "file_date": None,
    }


def apply(db: Session, file: ProjectFile, result: ReadResult) -> str:
    """Merge one reading into the draft revision. Returns a summary without values."""
    revision = draft_revision(db, file.project_id, None)
    by_key = {v.key: v for v in revision.values}
    added = conflicts = 0
    for cand in result.values:
        meta = info(cand.key)
        new = _candidate(cand.value, result, cand.source_ref, file)
        existing = by_key.get(cand.key)
        if existing is None:
            value = FichaValue(
                revision_id=revision.id, key=cand.key, group=meta.group, label_pt=meta.label_pt,
                value=cand.value, unit=meta.unit, personal_data=meta.personal, status="pending",
                source_type=result.source_type, source_ref=cand.source_ref, source_file_id=file.id,
            )  # fmt: skip
            db.add(value)
            by_key[cand.key] = value
            added += 1
            continue
        conflict = open_conflict(existing)
        if conflict is not None:
            others = [c for c in conflict.candidates if c["source_type"] != result.source_type]
            conflict.candidates = [*others, new]
            continue
        if existing.source_type == result.source_type:
            existing.value, existing.source_ref, existing.source_file_id = (
                cand.value,
                cand.source_ref,
                file.id,
            )  # a newer file of the same source
            continue
        if comparable(cand.key, existing.value) == comparable(cand.key, cand.value):
            continue  # the sources agree
        existing.conflicts.append(FichaConflict(candidates=[_as_candidate(existing), new]))
        existing.value, existing.status = None, "conflict"  # nobody chose yet
        conflicts += 1
    circuits = _replace_circuits(db, revision, file, result)
    db.flush()
    return _summary(len(result.values), added, circuits, conflicts, result.warnings)


def _replace_circuits(
    db: Session, revision: FichaRevision, file: ProjectFile, result: ReadResult
) -> int:
    if not result.circuits:
        return 0
    db.execute(delete(Circuit).where(Circuit.revision_id == revision.id))
    for row in result.circuits:
        fields = {k: v for k, v in row.fields.items() if k in _CIRCUIT_FIELDS}
        for k, v in fields.items():
            if isinstance(v, float):
                fields[k] = Decimal(str(v))
        db.add(
            Circuit(
                revision_id=revision.id, source_file_id=file.id, row_index=row.row_index,
                section=row.section, source_ref=row.source_ref, **fields,
            )
        )  # fmt: skip
    return len(result.circuits)


def _summary(read: int, added: int, circuits: int, conflicts: int, warnings: list[str]) -> str:
    parts = [f"{read} valores lidos ({added} novos)"]
    if circuits:
        parts.append(f"{circuits} troços")
    if conflicts:
        parts.append(f"{conflicts} conflito{'s' if conflicts > 1 else ''} para resolver")
    return " · ".join(parts + warnings)
