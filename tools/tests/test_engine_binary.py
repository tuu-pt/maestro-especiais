"""The fast binary scan finds exactly what the straightforward one found (same kinds)."""

import random

import pytest
from synthetic import make_nif

from anonymizer.detectors import detect_emails
from anonymizer.engine import _ACCENTS, _WHITESPACE, Seed, TextAnonymizer
from anonymizer.pseudonyms import PseudonymMap

NIF = make_nif("21234567")
SEEDS = [
    Seed("name", "Ana Silva Costa"),
    Seed("name", "Silva Costa Mendes"),
    Seed("name", "Rui Tavares"),
    Seed("nif", NIF),
    Seed("phone", "912345678"),
    Seed("cc", "12345678 9 ZZ4"),
    Seed("email", "ana.costa@exemplo.pt"),
    Seed("address", "Rua das Flores 12"),
]


def reference_hits(engine: TextAnonymizer, data: bytes) -> set[str]:
    """The original scan: every pattern with its lookbehind, on all three readings."""
    m = engine._get_matchers()
    kinds: set[str] = set()
    for text in (
        data.decode("latin-1"),
        data.decode("utf-16-le", "ignore"),
        data[1:].decode("utf-16-le", "ignore"),
    ):
        folded = _WHITESPACE.sub(" ", text.casefold().translate(_ACCENTS).replace("_", " "))
        if m.names:
            kinds |= {"name" for _ in m.names.finditer(folded)}
        if m.literals:
            kinds |= {engine._literal_seeds[h.group(0)][0] for h in m.literals.finditer(folded)}
        if m.digits:
            kinds |= {
                m.digit_keys[int((h.lastgroup or "d0")[1:])][0] for h in m.digits.finditer(text)
            }
        kinds |= {"email" for _ in detect_emails(text)}
    return kinds


@pytest.fixture
def engine() -> TextAnonymizer:
    return TextAnonymizer(PseudonymMap(), SEEDS)


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"0 0 m 100.5 200.25 l S", set()),
        (b"tel. 912 345 678 fim", {"phone"}),
        (b"tel. 912.345.678", {"phone"}),
        (b"x912345678", set()),  # glued to a letter: not the phone
        (b"9123456789", set()),  # longer number
        (f"NIF {NIF[:3]} {NIF[3:6]} {NIF[6:]}".encode(), {"nif"}),
        (b"cc 12345678 9 zz4", {"cc"}),
        (b"(ANA SILVA COSTA) Tj", {"name"}),
        (b"xana silva costa mendes", {"name"}),  # rejected at x, found overlapping after it
        (b"xana silva costax", set()),
        ("Técnico: Rui Tavares".encode("utf-16-le"), {"name"}),
        (b"\x01" + "Rui Tavares".encode("utf-16-le"), {"name"}),  # odd offset
        (b"mailto:ana.costa@exemplo.pt", {"email"}),
        (b"Rua das Flores 12, 1000", {"address"}),
        (b"@rua das flores 12", set()),  # glued to @: not the address
    ],
)
def test_same_kinds_as_the_reference(
    engine: TextAnonymizer, data: bytes, expected: set[str]
) -> None:
    assert set(engine.binary_hits(data)) == reference_hits(engine, data) == expected


def test_random_binaries_give_the_same_kinds(engine: TextAnonymizer) -> None:
    rng = random.Random(7)
    pieces = [
        b"912 345 678",
        b"912345678",
        NIF.encode(),
        b"Ana Silva Costa",
        b"ana  silva costa",
        b"silva costa mendes",
        b"rui tavares",
        b"ana.costa@exemplo.pt",
        b"rua das flores 12",
        "Rui Tavares".encode("utf-16-le"),
        b"12345678 9 ZZ4",
        b"x",
        b"@",
        b".",
        b" ",
        b"\x00",
    ]
    for _ in range(300):
        parts = []
        for _ in range(rng.randint(1, 12)):
            if rng.random() < 0.5:
                parts.append(rng.choice(pieces))
            else:
                parts.append(
                    bytes(rng.choice(b"0123456789 .-mlSx\x00\n") for _ in range(rng.randint(1, 30)))
                )
        data = b"".join(parts)
        assert set(engine.binary_hits(data)) == reference_hits(engine, data), data
