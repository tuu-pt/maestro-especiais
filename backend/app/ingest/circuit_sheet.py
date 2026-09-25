"""Reader of the TUU 09-Folha de Cálculo (.xls, one per circuit) and its link to the Tabela.

The sheet holds the detail of one circuit (IB, In, Iz, I2, section, length, voltage drop), read
by fixed cells (maps/folha09_*.yaml). It does not say which circuit it is: the two boards are in
the file name, compared with the Tabela by board name (boards.py). A sheet that does not match
exactly one circuit is left for a person. Values that differ from the circuit open a
FichaConflict on that circuit field; nothing is chosen (P1) and nothing is computed (P2).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Any

import xlrd
import yaml
from sqlalchemy.orm import Session

from app.ingest.base import json_number, to_number
from app.ingest.boards import Named, match_circuits, parse_sheet_name
from app.ingest.consolidate import draft_revision
from app.ingest.detect import fold
from app.ingest.pipeline import ReaderError
from app.models import Circuit, CircuitSheet, FichaConflict, FichaRevision, ProjectFile

MAPS = Path(__file__).parent / "maps"
SOURCE_TYPE = "calc_sheet"  # candidates only; the circuit itself stays "calc"


@dataclass(frozen=True)
class SheetMap:
    template: str
    sheets: tuple[str, ...]
    titles: dict[str, str]
    cells: dict[str, dict[str, Any]]


@dataclass
class SheetReading:
    template: str
    values: dict[str, dict[str, Any]]  # field → {"value": number, "ref": "proteccao!E9"}
    origin_hint: str | None = None
    destination_hint: str | None = None
    warnings: list[str] = field(default_factory=list)


@cache
def sheet_maps() -> tuple[SheetMap, ...]:
    maps = []
    for path in sorted(MAPS.glob("folha09_*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        signature = data["signature"]
        maps.append(
            SheetMap(
                template=data["template"],
                sheets=tuple(signature["sheets"]),
                titles=dict(signature.get("titles", {})),
                cells=dict(data["cells"]),
            )
        )
    return tuple(maps)


def _split(ref: str) -> tuple[str, int, int]:
    sheet, cell = ref.split("!")
    letters = "".join(c for c in cell if c.isalpha())
    column = 0
    for c in letters.upper():
        column = column * 26 + ord(c) - 64
    return sheet, int(cell[len(letters) :]) - 1, column - 1


def _cell(book: Any, ref: str) -> Any:
    name, row, col = _split(ref)
    sheet = book.sheet_by_name(name)
    if row >= sheet.nrows or col >= sheet.ncols:
        return None
    value = sheet.cell_value(row, col)
    return None if value == "" else value


def _matches(book: Any, sheet_map: SheetMap) -> bool:
    names = set(book.sheet_names())
    if not set(sheet_map.sheets) <= names:
        return False
    return all(
        expected in fold(_cell(book, ref) or "") for ref, expected in sheet_map.titles.items()
    )


def read(data: bytes, filename: str) -> SheetReading:
    try:
        book = xlrd.open_workbook(file_contents=data)
    except (xlrd.XLRDError, ValueError, OSError) as exc:
        raise ReaderError("09-Folha ilegível ou corrompida.") from exc
    sheet_map = next((m for m in sheet_maps() if _matches(book, m)), None)
    if sheet_map is None:
        raise ReaderError(
            "Modelo de 09-Folha desconhecido (folhas ou títulos diferentes): é preciso um novo "
            "mapa de células."
        )
    reading = SheetReading(template=sheet_map.template, values={})
    for name, spec in sheet_map.cells.items():
        number = to_number(_cell(book, spec["cell"]))
        if number is None:
            reading.warnings.append(f"Célula {spec['cell']} vazia ou sem número.")
            continue
        if "scale" in spec:
            number *= Decimal(str(spec["scale"]))
        reading.values[name] = {"value": json_number(number), "ref": spec["cell"]}
    hints = parse_sheet_name(filename)
    if hints is None:
        reading.warnings.append("O nome do ficheiro não indica o troço (origem-destino).")
    else:
        reading.origin_hint, reading.destination_hint = hints
    return reading


# ---------------------------------------------------------------- comparison


_NOISE = Decimal("1e-9")  # Excel floats: 82.65 arrives as 82.64999999999999


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(_NOISE, ROUND_HALF_UP).normalize()


def _places(number: Decimal) -> int:
    exponent = number.as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def same_reading(a: Any, b: Any, max_places: int = 2) -> bool:
    """Equal at the precision of the less precise value (at most 2 places) [A CONFIRMAR].

    29.8701 and 29.9 are the same reading; 0.76 and 0.9 are not. Only a comparison: nothing is
    written with the rounded value (P2).
    """
    x, y = _decimal(a), _decimal(b)
    places = min(_places(x), _places(y), max_places)
    step = Decimal(1).scaleb(-places)
    return x.quantize(step, ROUND_HALF_UP) == y.quantize(step, ROUND_HALF_UP)


def _open_conflict(circuit: Circuit, name: str) -> FichaConflict | None:
    return next((c for c in circuit.conflicts if c.field == name and c.resolved_at is None), None)


def compare_sheet(db: Session, sheet: CircuitSheet, circuit: Circuit) -> int:
    opened = 0
    for name, item in sheet.values.items():
        ours = getattr(circuit, name, None)
        if ours is None or item.get("value") is None or same_reading(ours, item["value"]):
            continue
        theirs = {
            "value": item["value"],
            "source_type": SOURCE_TYPE,
            "source_ref": f"09-Folha {sheet.origin_hint or '?'}-{sheet.destination_hint or '?'} · "
            f"{item['ref']}",
            "source_file_id": str(sheet.source_file_id) if sheet.source_file_id else None,
            "file_date": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        conflict = _open_conflict(circuit, name)
        if conflict is not None:  # a newer reading of the sheet replaces its candidate
            conflict.candidates = [c for c in conflict.candidates if c["source_type"] == "calc"] + [
                theirs
            ]
            continue
        circuit.conflicts.append(
            FichaConflict(
                circuit_id=circuit.id,
                field=name,
                candidates=[
                    {
                        "value": json_number(Decimal(str(ours))),
                        "source_type": "calc",
                        "source_ref": circuit.source_ref,
                        "source_file_id": str(circuit.source_file_id)
                        if circuit.source_file_id
                        else None,
                        "file_date": None,
                    },
                    theirs,
                ],
            )
        )
        opened += 1
    return opened


def drop_open_conflicts(db: Session, sheet: CircuitSheet, revision: FichaRevision) -> None:
    """Unresolved conflicts this sheet opened: they go when the sheet is linked elsewhere."""
    mine = str(sheet.source_file_id) if sheet.source_file_id else None
    for circuit in revision.circuits:
        for conflict in list(circuit.conflicts):
            ours = any(
                x["source_type"] == SOURCE_TYPE and x.get("source_file_id") == mine
                for x in conflict.candidates
            )
            if conflict.resolved_at is None and ours:
                circuit.conflicts.remove(conflict)
                db.delete(conflict)
    db.flush()


def link_and_compare(db: Session, revision: FichaRevision) -> int:
    """Link every sheet not linked by a person, then compare each linked sheet. New conflicts."""
    db.flush()
    db.expire(revision, ["circuits", "circuit_sheets"])
    circuits = {str(c.id): c for c in revision.circuits}
    named = [Named(str(c.id), c.origin or "", c.destination or "") for c in revision.circuits]
    opened = 0
    for sheet in revision.circuit_sheets:
        if sheet.link_status != "manual":
            ids = (
                match_circuits(sheet.origin_hint, sheet.destination_hint, named)
                if sheet.origin_hint and sheet.destination_hint
                else []
            )
            new_ids = [str(ids[0])] if len(ids) == 1 else []
            if new_ids != sheet.circuit_ids:
                drop_open_conflicts(db, sheet, revision)
            sheet.circuit_ids = new_ids
            sheet.link_status = "rule" if len(ids) == 1 else "unlinked"
        for cid in sheet.circuit_ids:
            if cid in circuits:
                opened += compare_sheet(db, sheet, circuits[cid])
    db.flush()
    return opened


def manual_links(revision: FichaRevision) -> dict[uuid.UUID, list[tuple[str | None, str | None]]]:
    """Boards of the circuits each sheet was linked to by a person, to keep across a new Tabela."""
    by_id = {str(c.id): c for c in revision.circuits}
    return {
        s.id: [(by_id[i].origin, by_id[i].destination) for i in s.circuit_ids if i in by_id]
        for s in revision.circuit_sheets
        if s.link_status == "manual"
    }


def restore_manual_links(
    db: Session,
    revision: FichaRevision,
    links: dict[uuid.UUID, list[tuple[str | None, str | None]]],
) -> None:
    db.flush()
    db.expire(revision, ["circuits", "circuit_sheets"])
    by_pair = {(c.origin, c.destination): str(c.id) for c in revision.circuits}
    for sheet in revision.circuit_sheets:
        if sheet.id in links:
            ids = [by_pair[p] for p in links[sheet.id] if p in by_pair]
            sheet.circuit_ids = ids
            if not ids:
                sheet.link_status = "unlinked"


def add_reading(db: Session, file: ProjectFile, reading: SheetReading) -> str:
    """Store the sheet in the draft revision, link it and compare. Summary without values."""
    revision = draft_revision(db, file.project_id, None)
    for old in list(revision.circuit_sheets):
        same_boards = (old.origin_hint, old.destination_hint) == (
            reading.origin_hint,
            reading.destination_hint,
        )
        if old.source_file_id == file.id or (reading.origin_hint and same_boards):
            db.delete(old)  # a newer file of the same circuit replaces the old reading
    db.add(
        CircuitSheet(
            revision_id=revision.id, source_file_id=file.id, origin_hint=reading.origin_hint,
            destination_hint=reading.destination_hint, template=reading.template,
            values=reading.values, link_status="unlinked", circuit_ids=[],
        )
    )  # fmt: skip
    opened = link_and_compare(db, revision)
    sheet = next(s for s in revision.circuit_sheets if s.source_file_id == file.id)
    parts = [f"{len(reading.values)} valores lidos"]
    if sheet.link_status == "rule":
        parts.append("associada ao troço pelo nome do ficheiro")
    elif not revision.circuits:
        parts.append("por associar: ainda não há Tabela de Cálculo")
    else:
        parts.append("por associar: escolha o troço na ficha")
    if opened:
        parts.append(f"{opened} conflito{'s' if opened > 1 else ''} para resolver")
    return " · ".join(parts + reading.warnings)
