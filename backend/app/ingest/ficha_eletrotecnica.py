"""Reader of the DGEG ficha eletrotécnica (.xlsm): fixed cells, one map per template version.

SPEC 8.2: if the version in R45 is not a known map, reading stops and asks for a new map.
"""

import io
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import openpyxl
import yaml

from app.ingest.base import Candidate, ReadResult, json_number, to_number
from app.ingest.keys import info
from app.ingest.pipeline import ReaderError

MAPS = Path(__file__).parent / "maps"


@dataclass(frozen=True)
class CellMap:
    template_version: str
    version_cell: str
    cells: dict[str, str]  # cell → ficha-base key


@cache
def cell_maps() -> dict[str, CellMap]:
    maps: dict[str, CellMap] = {}
    for path in sorted(MAPS.glob("fe_*.yaml")):
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        cells = {str(c): str(k) for c, k in data["cells"].items()}
        for key in cells.values():
            info(key)  # fails early on a key that is not in SPEC 7.2
        cm = CellMap(str(data["template_version"]), str(data["version_cell"]), cells)
        maps[cm.template_version] = cm
    return maps


def _version_cells() -> set[str]:
    return {m.version_cell for m in cell_maps().values()}


def _clean(key: str, raw: Any) -> Any:
    if raw is None:
        return None
    if info(key).numeric:
        number = to_number(raw)
        return json_number(number) if number is not None else str(raw).strip() or None
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)  # e.g. a NIF typed as a number
    text = str(raw).strip()
    return text or None


def read(data: bytes) -> ReadResult:
    workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True, keep_links=False)
    try:
        for sheet in workbook.worksheets:
            for cell in _version_cells():
                version = str(sheet[cell].value or "").strip()
                if not version.startswith("FE_v"):
                    continue
                cell_map = cell_maps().get(version)
                if cell_map is None:
                    raise ReaderError(
                        f"Versão do modelo DGEG desconhecida ({version[:40]}): é preciso um novo "
                        "mapa de células antes de ler esta ficha."
                    )
                return _read_sheet(sheet, cell_map)
    finally:
        workbook.close()
    raise ReaderError("Não foi encontrada a versão do modelo DGEG (célula R45).")


def _read_sheet(sheet: Any, cell_map: CellMap) -> ReadResult:
    result = ReadResult(
        source_type="ficha_eletrotecnica", template_version=cell_map.template_version
    )
    for cell, key in cell_map.cells.items():
        value = _clean(key, sheet[cell].value)
        if value is not None:
            result.values.append(Candidate(key, value, f"{sheet.title}!{cell}"))
    if not result.values:
        result.warnings.append("A ficha eletrotécnica não tem nenhum valor preenchido.")
    return result
