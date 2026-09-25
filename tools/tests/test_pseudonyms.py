from pathlib import Path

import pytest

from anonymizer.detectors import detect, nif_check_digit, nif_valid
from anonymizer.engine import Allowlist, Seed, TextAnonymizer
from anonymizer.pseudonyms import PseudonymMap
from anonymizer.textnorm import digits_only


def make_nif(first8: str) -> str:
    return first8 + str(nif_check_digit(first8))


NIF_A = make_nif("23456789")
NIF_B = make_nif("18765432")

# ---------------------------------------------------------------- PseudonymMap


def test_nif_pseudonym_is_reserved_invalid_and_keeps_format() -> None:
    m = PseudonymMap()
    spaced = m.pseudonym("nif", f"{NIF_A[:3]} {NIF_A[3:6]} {NIF_A[6:]}")
    plain = m.pseudonym("nif", NIF_A)

    assert digits_only(spaced) == plain
    assert spaced.count(" ") == 2
    assert plain.startswith("99999") and not nif_valid(plain)


def test_same_value_same_pseudonym_different_values_different_pseudonyms() -> None:
    m = PseudonymMap()
    assert m.pseudonym("nif", NIF_A) == m.pseudonym("nif", NIF_A)
    assert m.pseudonym("nif", NIF_A) != m.pseudonym("nif", NIF_B)


def test_names_are_injective_for_hundreds_of_people() -> None:
    m = PseudonymMap()
    pseudonyms = {m.pseudonym("name", f"Pessoa Real {i:03d}") for i in range(500)}
    assert len(pseudonyms) == 500


@pytest.mark.parametrize(
    ("kind", "value", "shape"),
    [
        ("phone", "+351 912 345 678", r"^\+351 9\d\d \d{3} \d{3}$"),
        ("phone", "22 123 45 67", r"^2\d \d{3} \d\d \d\d$"),
        ("cc", "12345678 9 ZX4", r"^\d{8} \d ZZ\d$"),
        ("email", "Maria.Ferreira@eng.pt", r"^pessoa\d{3}@example\.com$"),
        ("postal_code", "4000-123", r"^0000-\d{3}$"),
        ("dgeg_oet", "15678", r"^0\d{4}$"),
        ("gps", "41.1579, -8.6291", r"^0\.\d{4}, -0\.\d{4}$"),
        ("address", "RUA DAS FLORES, 12", r"^RUA EXEMPLO \d+$"),
        ("user_path", "joao.almeida", r"^utilizador\d\d$"),
    ],
)
def test_pseudonyms_keep_the_shape(kind: str, value: str, shape: str) -> None:
    import re

    assert re.match(shape, PseudonymMap().pseudonym(kind, value))


@pytest.mark.parametrize(
    ("kind", "value", "context"),
    [
        ("nif", NIF_A, "NIF: {}"),
        ("phone", "912345678", "Tel. {}"),
        ("phone", "+351 225 123 456", "Tel. {}"),
        ("cc", "12345678 9 ZX4", "CC n.º {}"),
        ("email", "a@b.pt", "{}"),
        ("postal_code", "4000-123", "{} Porto"),
        ("dgeg_oet", "15678", "OET n.º {}"),
        ("gps", "41.1579, -8.6291", "GPS {}"),
        ("gps", "41°09'28.4\"N 8°37'44.8\"W", "{}"),
        ("address", "Rua das Flores, 12", "{}"),
        ("name", "Maria Sousa Ferreira", "Eng.ª {}"),
        ("user_path", "joao", r"C:\Users\{}\Desktop"),
    ],
)
def test_pseudonyms_are_never_detected_as_personal_data(
    kind: str, value: str, context: str
) -> None:
    pseudonym = PseudonymMap().pseudonym(kind, value)
    assert detect(context.format(pseudonym)) == []


def test_names_keep_case_and_initial_style() -> None:
    m = PseudonymMap()
    full = m.pseudonym("name", "Maria Sousa Ferreira")
    assert m.pseudonym("name", "MARIA SOUSA FERREIRA") == full.upper()
    first, *_, last = full.split()
    from anonymizer.pseudonyms import render

    assert render("name", "M. Ferreira", m.number("name", "Maria Sousa Ferreira")) == (
        f"{first[0]}. {last}"
    )


def test_table_round_trip_keeps_pseudonyms(tmp_path: Path) -> None:
    path = tmp_path / "private" / "map.json"
    m = PseudonymMap()
    before = [m.pseudonym("nif", NIF_A), m.pseudonym("name", "João Pedro Almeida")]
    m.save(path)

    loaded = PseudonymMap.load(path)

    assert [loaded.pseudonym("nif", NIF_A), loaded.pseudonym("name", "João Pedro Almeida")] == (
        before
    )
    assert loaded.pseudonym("nif", NIF_B) not in before


# ---------------------------------------------------------------- TextAnonymizer

JOAO = Seed("name", "João Pedro Almeida")
MARIA = Seed("name", "Maria Sousa Ferreira")


def test_name_seed_is_replaced_in_every_variant_consistently() -> None:
    engine = TextAnonymizer(PseudonymMap(), [JOAO, MARIA])
    text = (
        "Requerente João Pedro Almeida; JOAO PEDRO ALMEIDA; João Almeida; "
        "o técnico M. Ferreira (Maria Sousa Ferreira)."
    )

    out, reps = engine.anonymize(text)

    for real in ("João", "JOAO", "Almeida", "ALMEIDA", "Ferreira", "Maria"):
        assert real not in out
    pseudo = engine.mapping.pseudonym("name", JOAO.value)
    assert pseudo in out and pseudo.upper() in out
    assert {r.kind for r in reps} == {"name"}


def test_numbers_in_other_formats_share_the_pseudonym() -> None:
    engine = TextAnonymizer(PseudonymMap(), [Seed("nif", NIF_A)])
    out, _ = engine.anonymize(f"NIF {NIF_A[:3]} {NIF_A[3:6]} {NIF_A[6:]} e ainda {NIF_A}.")
    pseudo = engine.mapping.pseudonym("nif", NIF_A)

    assert NIF_A[:3] not in out
    assert out.count(pseudo) == 1 and out.count(f"{pseudo[:3]} {pseudo[3:6]}") == 1


def test_different_oet_numbers_stay_different_c3() -> None:
    engine = TextAnonymizer(PseudonymMap())
    forms, _ = engine.anonymize("OET n.º 15678")
    mdj, _ = engine.anonymize("OET n.º 15687")

    assert forms != mdj
    assert "15678" not in forms and "15687" not in mdj


def test_heuristic_name_becomes_a_seed_for_later_text() -> None:
    engine = TextAnonymizer(PseudonymMap())
    engine.anonymize("Desenhou: Rui Manuel Costa")
    out, reps = engine.anonymize("revisto por Rui Costa")

    assert "Rui" not in out and "Costa" not in out
    assert reps[0].source == "seed"


def test_short_numeric_seed_is_not_replaced_without_context() -> None:
    engine = TextAnonymizer(PseudonymMap(), [Seed("dgeg_oet", "4321")])
    out, reps = engine.anonymize("Potência de 4321 W")

    assert out == "Potência de 4321 W" and reps == []
    out, _ = engine.anonymize("inscrito na DGEG com o n.º 4321")
    assert "4321" not in out


def test_allowlist_keeps_confirmed_false_positives() -> None:
    allow = Allowlist.from_items([("address", "Rua Nova de Exemplo Técnico")])
    engine = TextAnonymizer(PseudonymMap(), allowlist=allow)
    text = "ver Rua Nova de Exemplo Técnico"

    assert engine.anonymize(text)[0] == text


def test_allowlist_also_wins_over_the_table_of_earlier_runs() -> None:
    """A value an earlier run put in the table is kept once a person allows it."""
    mapping = PseudonymMap()
    mapping.number("address", "Santo Exemplo dos Olivais")  # taken for an address before
    text = "Freguesia: Santo Exemplo dos Olivais"
    assert "Olivais" not in TextAnonymizer.for_verification(mapping).anonymize(text)[0]

    allow = Allowlist.from_items([("address", "Santo Exemplo dos Olivais")])
    engine = TextAnonymizer(mapping, allowlist=allow)
    engine.include_table()

    assert engine.anonymize(text)[0] == text
    assert TextAnonymizer.for_verification(mapping, allow).residuals(text) == []


def test_residuals_find_real_values_and_accept_the_output() -> None:
    mapping = PseudonymMap()
    engine = TextAnonymizer(mapping, [JOAO, Seed("nif", NIF_A), Seed("email", "joao@mail.pt")])
    original = f"João Almeida, NIF {NIF_A}, joao@mail.pt, Tel. 912 345 678, 4000-123 Porto"
    out, _ = engine.anonymize(original)

    checker = TextAnonymizer.for_verification(mapping)
    assert checker.residuals(out) == []
    kinds = {r.kind for r in checker.residuals(original)}
    assert {"name", "nif", "phone", "postal_code"} <= kinds
    assert "email" not in kinds and "joao@mail.pt" in out  # emails are kept


def test_emails_are_kept_and_their_digits_are_not_taken_for_numbers() -> None:
    engine = TextAnonymizer(PseudonymMap(), [Seed("email", "joao@mail.pt")])
    text = "Contactos: joao@mail.pt e 912345678@sms.pt"
    out, reps = engine.anonymize(text)
    assert out == text and reps == []


def test_short_form_of_a_known_name_is_the_same_person() -> None:
    engine = TextAnonymizer(PseudonymMap(), [Seed("name", "Maria Ferreira"), MARIA])
    out, _ = engine.anonymize("Eng.ª Maria Ferreira; M. Ferreira; Maria Sousa Ferreira")
    full = engine.mapping.pseudonym("name", MARIA.value)
    first, *_, last = full.split()

    assert f"{first} {last}" in out and f"{first[0]}. {last}" in out and full in out
    assert "Ferreira" not in out


def test_an_address_in_capitals_passes_the_verification() -> None:
    # Cover pages and drawing title blocks: the pseudonym comes out as "RUA EXEMPLO n".
    mapping = PseudonymMap()
    engine = TextAnonymizer(mapping)
    out, reps = engine.anonymize("OBRA: MORADIA · RUA DAS CAMÉLIAS, 12 · CEDOFEITA")
    assert [r.kind for r in reps] == ["address"] and "RUA EXEMPLO" in out
    assert TextAnonymizer.for_verification(mapping).residuals(out) == []
