"""Board name normalization, with every real pair of R1 and R2 (board names, not personal data)."""

import pytest

from app.ingest.boards import Named, canonical, core, match_circuits, parse_sheet_name, same_board

R1_CIRCUITS = [
    Named(i, o, d)
    for i, (o, d) in enumerate(
        [
            ("Portinhola", "QE"),
            ("Q.E.G.", "Q.P.1.1"),
            ("Q.E.G.", "Q.P.1.2"),
            ("Q.E.G.", "Q.P.2.1"),
            ("Q.E.G.", "Q.P.2.2"),
            ("Q.E.G.", "Q.P.3.1"),
        ]
    )
]
R2_CIRCUITS = [
    Named(i, o, d)
    for i, (o, d) in enumerate(
        [
            ("Portinhola", "Q.E.G."),
            ("Q.E.G.", "Q.P.ADMIN"),
            ("Q.E.G.", "Q.P.ATRIO"),
            ("Q.E.G.", "Q.P.CAFETARIA"),
            ("Q.E.G.", "Q.P.REGIE"),
            ("Q.E.G.", "Q.P.BIB.INFANT."),
            ("Q.E.G.", "Q.P.BIB.ADULTOS"),
            ("Q.E.G.", "Q.P.REPROGRAFIA"),
            ("Q.P.REPROGRAFIA", "Q.P.ARQUIVO"),
            ("Q.E.G.", "Q.P.EXTERIOR"),
            ("Q.E.G.", "Q.AVAC"),
            ("Q.FV.AC", "Q.P.ADMIN"),
            ("Q.E.G.", "UPS 10kVA"),
            ("Q.E.G.", "UPS 30kVA Desenf"),
            ("Q.UPS 10kVA", "Q.P.UPS.P-1"),
            ("Q.P.EXTERIOR", "CVE 1"),
            ("Q.P.EXTERIOR", "CVE 2"),
            ("Q.P.EXTERIOR", "CVE 3"),
            ("Q.P.EXTERIOR", "CVE 4"),
            ("Q.P.EXTERIOR", "CVE 5"),
        ]
    )
]


def test_canonical_and_core() -> None:
    assert canonical("Q.P.BIB.INFANT.") == "QPBIBINFANT"
    assert core("Q.P.BIB.INFANT.") == "BIBINFANT"
    assert core("Q.P.ATRIO") == core("ATRIO") == "ATRIO"
    assert core("Q.E.G.") == core("QE") == core("QEG") == "QEG"
    assert core("Portinhola") == core("Port") == core("ARM") == "PORTINHOLA"
    assert core("Quadro Q.AVAC") == "AVAC"
    assert same_board("QP.ADMIN", "Q.P.ADMIN") and not same_board("Q.P.ADMIN", "Q.P.ATRIO")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("09-Folha de Cálculo Port-QE.xls", ("Port", "QE")),
        ("09-Folha de Cálculo QE-QP1.1.xls", ("QE", "QP1.1")),
        ("09-Folha de Cálculo QUPS-QUPS.P-1.xls", ("QUPS", "QUPS.P-1")),
        ("09-Folha de Cálculo QP.REPRO-QP.ARQUIVO.xls", ("QP.REPRO", "QP.ARQUIVO")),
        ("Folha de calculo QEG-ATRIO.xls", ("QEG", "ATRIO")),
        ("09-Folha de Cálculo.xls", None),
        ("troco sem hifen.xls", None),
    ],
)
def test_sheet_names(filename: str, expected: tuple[str, str] | None) -> None:
    assert parse_sheet_name(filename) == expected


def sheet(name: str, circuits: list[Named]) -> list[object]:
    parsed = parse_sheet_name(f"09-Folha de Cálculo {name}.xls")
    assert parsed is not None
    return match_circuits(*parsed, circuits)


@pytest.mark.parametrize(
    ("name", "index"),
    [
        ("Port-QE", 0),
        ("QE-QP1.1", 1),
        ("QE-QP1.2", 2),
        ("QE-QP2.1", 3),
        ("QE-QP2.2", 4),
        ("QE-QP3.1", 5),
    ],
)
def test_every_r1_sheet_finds_its_circuit(name: str, index: int) -> None:
    assert sheet(name, R1_CIRCUITS) == [index]


@pytest.mark.parametrize(
    ("name", "index"),
    [
        ("ARM-QEG", 0),
        ("QEG-ATRIO", 2),
        ("QEG-Q.AVAC", 10),
        ("QEG-Q.P.CAFETARIA", 3),
        ("QEG-QP.ADMIN", 1),
        ("QEG-QP.BIB.ADULTOS", 6),
        ("QEG-QP.BIB.INF", 5),
        ("QEG-QP.EXTERIOR", 9),
        ("QEG-QP.REPRO", 7),
        ("QEG-REGIE", 4),
        ("QEG-UPS10", 12),
        ("QEG-UPS30", 13),
        ("QFV.AC-QP.ADMIN", 11),
        ("QP.REPRO-QP.ARQUIVO", 8),
        ("QUPS-QUPS.P-1", 14),
    ],
)
def test_every_r2_sheet_finds_its_circuit(name: str, index: int) -> None:
    assert sheet(name, R2_CIRCUITS) == [index]


def test_one_sheet_for_five_equal_circuits_is_ambiguous() -> None:
    assert sheet("QPEXT-CVE", R2_CIRCUITS) == [15, 16, 17, 18, 19]  # left for a person


def test_unknown_boards_match_nothing() -> None:
    assert sheet("QEG-QP.PISO9", R2_CIRCUITS) == []
    assert match_circuits("", "Q.P.ADMIN", R2_CIRCUITS) == []
