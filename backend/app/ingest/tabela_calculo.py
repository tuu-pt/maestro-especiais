"""Reader of the TUU Tabela de Cálculo (.xlsx): one Circuit per line (SPEC 7.1, 8.2).

Columns are found by the text of their header, never by position: some are empty (IΔn),
and their order changes between projects. The header can have a second line under a group
("TIPO C" → "Norma [kVA]", "TOTAL INSTALADO"…), as in R1 and R2. Section rows ("ENTRADA DE
ENERGIA", "EDIFÍCIO") are not circuits. The reader compares nothing and computes nothing (P2).
"""

import io
import re
from typing import Any

import openpyxl

from app.ingest.base import Candidate, CircuitRow, ReadResult, json_number, to_number
from app.ingest.detect import fold
from app.ingest.pipeline import ReaderError

# (field, pattern on the folded header). Order matters: the first pattern that matches wins.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("origin", r"^origem"),
    ("destination", r"^destino"),
    ("vd_section_pct", r"(q\.?d\.?t|queda|\bdu\b).*(troco|parcial)"),
    ("vd_upstream_pct", r"(q\.?d\.?t|queda|\bdu\b).*(montante|anterior)"),
    ("vd_total_pct", r"(q\.?d\.?t|queda|\bdu\b).*(total|acumulad)"),
    ("iz145_a", r"1[.,]45"),
    ("idn_ma", r"^i\s?[δ∆d]\s?n\b|diferencial"),
    ("ib_a", r"^ib\b"),
    ("in_a", r"^in\b"),
    ("iz_a", r"^iz\b"),
    ("i2_a", r"^i2\b"),
    # The circuit's power: "TOTAL INSTALADO" (norma + socorro + segurança) [A CONFIRMAR].
    ("kva", r"^total instalado|^pot|^kva"),
    ("voltage_v", r"^tensao|^u \(v\)"),
    ("protection_type", r"^(tipo de )?prote[cç]|fusivel|disjuntor"),
    ("breaking_capacity_ka", r"^pdc|poder de corte"),
    ("length_m", r"^comprim|^l \(m\)"),
    ("pole_type", r"^polo|^n\.?o? de polos|monopolar|multipolar"),
    ("installation", r"^instala|^montagem|^tipo de instala|enterrad|esteira|embebid"),
    ("phases", r"^fases|^n\.?o? (de )?fases|monofasic|trifasic"),
    ("insulation", r"^isolament"),
    ("conductor", r"^(condutor|material)( \(.*\))?$|cobre|alumin"),
    ("ref_method", r"^metodo|^met\.? ref"),
    ("rtiebt_table", r"rtiebt"),
    ("cable_raw", r"^cabo|^canaliza|designa"),
)
NUMERIC = {
    "kva", "voltage_v", "ib_a", "in_a", "idn_ma", "iz_a", "i2_a", "iz145_a", "length_m",
    "vd_section_pct", "vd_upstream_pct", "vd_total_pct", "breaking_capacity_ka",
}  # fmt: skip
_BOARD = re.compile(r"^q\b|^q\.|^quadro", re.I)
# Known columns that the Circuit does not keep (SPEC 7.1): no warning for them.
KNOWN_UNUSED = re.compile(r"^norma|^socorro|^seguranca|quadros|^tipo c$|^imped|corte geral")


def match_column(header: str) -> str | None:
    text = fold(header)
    for field, pattern in COLUMNS:
        if re.search(pattern, text):
            return field
    return None


def _enum(field: str, raw: Any) -> Any:
    text = fold(raw)
    if not text:
        return None
    if field == "protection_type":
        return {"d": "D", "f": "F"}.get(text[0])
    if field == "pole_type":
        if text.startswith(("mon", "uni", "1")):
            return "MON"
        return "MUL" if text.startswith(("mul", "tri", "tetra", "bi", "3", "4")) else None
    if field == "installation":
        code = text[:3].upper()
        return code if code in {"TUB", "EST", "ENT"} else ("AR" if text.startswith("ar") else None)
    if field == "phases":
        if text.startswith(("tri", "3")):
            return 3
        return 1 if text.startswith(("mon", "1")) else None
    if field == "conductor":
        return {"cu": "Cu", "al": "Al"}.get(text[:2])
    return str(raw).strip()


def _value(field: str, raw: Any) -> Any:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if field in NUMERIC:
        return to_number(raw)
    if field in {"protection_type", "pole_type", "installation", "phases", "conductor"}:
        return _enum(field, raw)
    return str(raw).strip()


def _find_header(rows: list[tuple[Any, ...]]) -> int | None:
    for index, row in enumerate(rows[:40]):
        words = {fold(c) for c in row if c is not None}
        if any(w.startswith("origem") for w in words) and any(
            w.startswith("destino") for w in words
        ):
            return index
    return None


def _headers(rows: list[tuple[Any, ...]], index: int) -> tuple[list[str], int]:
    """Header text per column and the index of the first data row.

    A next row with text and no numbers is the second line of the header: where it has text,
    it names the column (under "TIPO C": "Norma [kVA]", "TOTAL INSTALADO"…).
    """
    main = ["" if c is None else str(c).strip() for c in rows[index]]
    sub = rows[index + 1] if index + 1 < len(rows) else ()
    texts = [str(c).strip() for c in sub if c is not None and str(c).strip()]
    if len(texts) < 2 or any(to_number(t) is not None for t in texts):
        return main, index + 1
    merged = []
    for i in range(max(len(main), len(sub))):
        below = str(sub[i]).strip() if i < len(sub) and sub[i] is not None else ""
        merged.append(below or (main[i] if i < len(main) else ""))
    return merged, index + 2


def read(data: bytes) -> ReadResult:
    # Not read-only: read-only mode skips empty rows and the line numbers would drift.
    workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = list(sheet.iter_rows(min_row=1, values_only=True))
            header_index = _find_header(rows)
            if header_index is not None:
                return _read_table(sheet.title, rows, header_index)
    finally:
        workbook.close()
    raise ReaderError("Não foi encontrado o cabeçalho da Tabela de Cálculo (ORIGEM / DESTINO).")


def _read_table(title: str, rows: list[tuple[Any, ...]], header_index: int) -> ReadResult:
    result = ReadResult(source_type="calc")
    columns: dict[int, str] = {}
    headers, first_data = _headers(rows, header_index)
    for position, header in enumerate(headers):
        if not header:
            continue
        field = match_column(header)
        if field is None and KNOWN_UNUSED.search(fold(header)):
            continue
        if field is None or field in columns.values():
            label = " ".join(header.split())[:60]
            result.warnings.append(f"Coluna não reconhecida: «{label}».")
            continue
        columns[position] = field
    section: str | None = None
    for offset, row in enumerate(rows[first_data:], start=first_data + 1):
        cells = [c for c in row if c is not None and str(c).strip()]
        if not cells:
            continue
        fields = {f: _value(f, row[p]) for p, f in columns.items() if p < len(row)}
        if len(cells) == 1 and isinstance(cells[0], str) and not fields.get("destination"):
            section = cells[0].strip()  # "ENTRADA DE ENERGIA", "EDIFÍCIO"
            continue
        if not fields.get("origin") and not fields.get("destination"):
            continue
        result.circuits.append(
            CircuitRow(
                row_index=offset,
                source_ref=f"{title}!linha {offset}",
                section=section,
                fields={k: v for k, v in fields.items() if v is not None},
            )
        )
    if not result.circuits:
        result.warnings.append("A Tabela de Cálculo não tem troços.")
    result.values = _candidates(result.circuits)
    return result


def _candidates(circuits: list[CircuitRow]) -> list[Candidate]:
    """Ficha-base values that come from the table (SPEC 7.2): read, never computed."""
    if not circuits:
        return []
    out: list[Candidate] = []
    first = circuits[0]  # the first line: the supply (SPEC 7.2, Alimentação)
    kva = first.fields.get("kva")
    if kva is not None:
        out.append(Candidate("ele.potencia_alimentar_kva", json_number(kva), first.source_ref))
    phases = first.fields.get("phases")
    if phases in (1, 3):
        out.append(Candidate("ele.entrada", "Trif" if phases == 3 else "Mono", first.source_ref))
    boards: list[str] = []
    for c in circuits:
        for name in (c.fields.get("origin"), c.fields.get("destination")):
            if name and _BOARD.search(str(name)) and name not in boards:
                boards.append(str(name))
    if boards:
        out.append(Candidate("ele.quadros", boards, "Tabela de Cálculo · origens e destinos"))
    cables = list(
        dict.fromkeys(str(c.fields["cable_raw"]) for c in circuits if "cable_raw" in c.fields)
    )
    if cables:
        out.append(Candidate("ele.cabos", cables, "Tabela de Cálculo · coluna do cabo"))
    return out
