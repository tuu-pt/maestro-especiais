"""Facts read from every piece, without the LLM (Phase 5, task 3), on the fixtures of R1/R2."""

from collections import defaultdict
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from reference_projects import FIXTURES, have_fixtures

from app.ingest.detect import detect
from app.validation.extract import EXTRACTORS, Sources
from app.validation.extract import files as file_pieces
from app.validation.extract.text import (
    BOARD_NAMES,
    CABLE,
    POWER,
    POWER_EXISTING,
    QTY_BOARDS,
    QTY_EV,
    QTY_PV_MODULES,
)
from app.validation.pieces import Fact, Piece
from app.validation.quantities import count, to_int

WRITTEN = {"mdj_docx": "MDJ", "cte_docx": "CTE"}


# ---------------------------------------------------------------- quantities


@pytest.mark.parametrize(
    ("text", "value"),
    [("6", 6), ("seis", 6), ("dezasseis", 16), ("catorze", 14), ("vinte e dois", 22),
     ("cento e vinte", 120), ("muitos", None)],
)  # fmt: skip
def test_numbers_in_digits_or_in_words(text: str, value: int | None) -> None:
    assert to_int(text) == value


def test_the_multiplication_written_in_the_cte_is_read_c8() -> None:
    q = count(
        "composto por três pedestais com capacidade de dois carregadores individuais em cada.",
        r"carregador(?:es)?", container=r"(?:pedestal|pedestais)",
    )  # fmt: skip

    assert q is not None and q.value == 6 and q.how.startswith("3 \u00d7 2")
    assert q.text == "três pedestais com capacidade de dois carregadores individuais em cada"


def test_a_part_of_the_whole_is_not_the_quantity() -> None:
    q = count("estão previstos 5 carregadores, dos quais 2 carregadores são obrigatórios",
              r"carregador(?:es)?")  # fmt: skip
    only_part = count("dos quais 2 carregadores são obrigatórios", r"carregador(?:es)?")

    assert q is not None and q.value == 5 and only_part is None


def test_nothing_else_is_multiplied() -> None:
    q = count("dois quadros parciais no Piso 1 e seis quadros elétricos", r"quadros\s+eletricos")
    assert q is not None and q.value == 6


# ---------------------------------------------------------------- pieces of R1 and R2


class _Store(dict[str, bytes]):
    def get(self, key: str) -> bytes:  # type: ignore[override]
        return self[key]


@cache
def facts_of(code: str) -> dict[str, dict[str, list[Fact]]]:
    """kind -> key -> facts, reading the first file of each kind of the reference project."""
    store = _Store()
    files: dict[str, Any] = {}

    def stale(path: Path) -> bool:  # old versions and signed copies come last
        return any(w in path.as_posix().lower() for w in ("/old/", "signed", "(1)"))

    for path in sorted((FIXTURES / code).rglob("*"), key=lambda p: (stale(p), str(p))):
        if not path.is_file() or path.suffix.lower() not in (".xlsx", ".xlsm", ".pdf", ".docx"):
            continue
        data = path.read_bytes()
        found = detect(path.name, data).kind
        kind = file_pieces.KIND_OF_FILE.get(found) or WRITTEN.get(found)
        if kind and kind not in files:
            store[str(path)] = data
            files[kind] = SimpleNamespace(storage_key=str(path))
    sources = cast(Sources, SimpleNamespace(db=SimpleNamespace(get=lambda _, i: files[i]),
                                            store=store))  # fmt: skip
    out: dict[str, dict[str, list[Fact]]] = {}
    for kind in files:
        origin = "existing" if kind in WRITTEN.values() else "file"
        read = EXTRACTORS.get(f"{origin}:{kind}") or EXTRACTORS[origin]
        piece_data = read(sources, Piece(ref=kind, kind=kind, origin=origin, content_hash="",
                                   file_id=kind))  # fmt: skip
        by_key: dict[str, list[Fact]] = defaultdict(list)
        for f in piece_data.facts:
            by_key[f.key].append(f)
        out[kind] = by_key
    return out


def values(code: str, kind: str, key: str) -> list[Any]:
    return [f.value for f in facts_of(code)[kind].get(key, [])]


needs_fixtures = pytest.mark.skipif(not have_fixtures(), reason="data/fixtures/R1 e R2")


@needs_fixtures
def test_r1_control_the_power_and_the_boards_agree() -> None:
    assert values("R1", "FICHA_ELE", POWER) == [34.5]
    assert values("R1", "CALC", POWER) == [34.5]
    assert values("R1", "MDJ", POWER) == [34.5]
    assert values("R1", "IDENTIFICACAO", POWER) == ["34,50"]  # compared as a number
    assert values("R1", "CALC", QTY_BOARDS) == values("R1", "MQT", QTY_BOARDS) == [6]
    assert values("R1", "CTE", QTY_BOARDS) == [6]  # «seis quadros elétricos»
    assert values("R1", "MDJ", QTY_BOARDS) == []  # the MDJ names them, it does not count them
    assert values("R1", "MDJ", BOARD_NAMES) == values("R1", "CALC", BOARD_NAMES)


@needs_fixtures
def test_r1_c1_the_wires_of_the_mdj_and_of_the_cte() -> None:
    assert "H07V-K" in values("R1", "MDJ", CABLE) and "H07V-U" not in values("R1", "MDJ", CABLE)
    assert "H07V-U" in values("R1", "CTE", CABLE) and "H07V-U" in values("R1", "CALC", CABLE)
    where = next(f for f in facts_of("R1")["MDJ"][CABLE] if f.value == "H07V-K").locator
    assert where["section"] == "canalizacoes.canalizacoes_embebidas_ou_ocultas"


@needs_fixtures
def test_r1_c3_the_technician_is_read_but_never_shown() -> None:
    oet = {k: facts_of("R1")[k].get("tec.oet", []) for k in ("MDJ", "CTE", "IDENTIFICACAO")}

    assert all(len(v) == 1 for v in oet.values())
    assert all(f.personal and f.display() == "•••" for v in oet.values() for f in v)


@needs_fixtures
def test_r2_c6_power_in_the_ficha_the_cte_and_the_table() -> None:
    assert values("R2", "FICHA_ELE", POWER) == [180]
    assert values("R2", "CALC", POWER) == [200]
    assert values("R2", "CTE", POWER) == [200.0]
    assert values("R2", "CTE", POWER_EXISTING) == [66.0]  # «atualmente numa ligação BTE de 66kVA»
    assert values("R2", "MDJ", POWER) == []  # C6: the MDJ has no value


@needs_fixtures
def test_r2_c8_chargers_in_each_piece() -> None:
    assert values("R2", "MDJ", QTY_EV) == [5]
    assert values("R2", "CTE", QTY_EV) == [6]
    assert values("R2", "CALC", QTY_EV) == [5]  # troços CVE 1 … CVE 5
    assert values("R2", "LPU", QTY_EV) == [5.0]  # the pedestals are not chargers
    note = facts_of("R2")["CTE"][QTY_EV][0].note or ""
    assert "3 \u00d7 2" in note and "capacidade" in note


@needs_fixtures
def test_r2_c9_three_ways_of_writing_the_cables() -> None:
    assert "FXZ1" in values("R2", "MDJ", CABLE) and "FXZ1" in values("R2", "CTE", CABLE)
    assert "RZ1-K (AS)" in values("R2", "CALC", CABLE)
    assert "XZ1(frt,zh)" in values("R2", "LPU", CABLE)


@needs_fixtures
def test_r2_the_boards_of_the_table_and_of_the_lpu_differ_as_already_known() -> None:
    assert values("R2", "CALC", QTY_BOARDS) == [14]
    assert values("R2", "LPU", QTY_BOARDS) == [16]
    assert values("R2", "CTE", QTY_BOARDS) == [16]  # «dezasseis quadros elétricos»
    assert values("R2", "LPU", QTY_PV_MODULES) == values("R2", "MDJ", QTY_PV_MODULES) == [40]


@needs_fixtures
def test_r1_c4_the_index_and_the_pages_of_the_drawings_are_read() -> None:
    drawings = facts_of("R1")["DRAWINGS"]
    assert drawings["pd.n_paginas_pdf"][0].value == 16
    assert len(drawings["pd.indice"][0].value) == 17


def test_extractors_are_registered_for_every_kind_of_piece() -> None:
    for kind in ("FICHA_ELE", "CALC", "MQT", "LPU", "DRAWINGS", "IDENTIFICACAO", "TERMO"):
        assert f"file:{kind}" in EXTRACTORS
    assert {"assembled", "existing"} <= set(EXTRACTORS)
    assert Path(__file__).exists()
