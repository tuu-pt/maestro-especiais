import pytest

from anonymizer.detectors import detect, in_portugal, nif_check_digit, nif_valid
from anonymizer.textnorm import fold, original_span


def make_nif(first8: str) -> str:
    return first8 + str(nif_check_digit(first8))


NIF = make_nif("23456789")


def kinds(text: str) -> list[tuple[str, str]]:
    return [(d.kind, d.value) for d in detect(text)]


# ---------------------------------------------------------------- NIF


def test_nif_checksum() -> None:
    assert nif_valid(NIF)
    assert not nif_valid(NIF[:8] + str((int(NIF[8]) + 1) % 10))
    assert not nif_valid("023456789")


@pytest.mark.parametrize(
    "text",
    [
        f"NIF: {NIF}",
        f"NIF {NIF[:3]} {NIF[3:6]} {NIF[6:]}",
        f"contribuinte n.º {NIF}",
        f"({NIF})",
        NIF,  # valid checksum without context
    ],
)
def test_nif_is_detected(text: str) -> None:
    assert [k for k, _ in kinds(text)] == ["nif"]


def test_nif_context_wins_over_invalid_checksum() -> None:
    bad = NIF[:8] + str((int(NIF[8]) + 1) % 10)
    assert kinds(f"NIF: {bad}")[0][0] == "nif"


def test_reserved_nif_pseudonym_is_ignored() -> None:
    reserved = "99999001" + str((nif_check_digit("99999001") + 1) % 10)
    assert detect(f"NIF {reserved}") == []


# ---------------------------------------------------------------- phone


@pytest.mark.parametrize(
    "text",
    [
        "Tel.: 912 345 678",
        "telemóvel 912345678",
        "+351 225 123 456",
        "00351 912345678",
        "Contacto: 22 123 45 67",
        "fax 21 1234567",
    ],
)
def test_phone_is_detected(text: str) -> None:
    assert [k for k, _ in kinds(text)] == ["phone"]


def test_reserved_phone_pseudonym_is_ignored() -> None:
    assert detect("Tel. 900 001 234") == []
    assert detect("Tel. 200001234") == []


# ---------------------------------------------------------------- CC


@pytest.mark.parametrize(
    "text",
    ["CC n.º 12345678 9 ZZ4", "12345678 9ZZ4", "Cartão de Cidadão: 12345678", "BI 1234567"],
)
def test_cc_is_detected(text: str) -> None:
    assert [k for k, _ in kinds(text)] == ["cc"]


# ---------------------------------------------------------------- email, postal code


def test_email_and_postal_code() -> None:
    assert kinds("maria.ferreira@eng.pt, 4000-123 Porto") == [
        ("email", "maria.ferreira@eng.pt"),
        ("postal_code", "4000-123"),
    ]


def test_reserved_email_and_postal_code_are_ignored() -> None:
    assert detect("pessoa001@example.com 0000-001") == []


# ---------------------------------------------------------------- GPS


@pytest.mark.parametrize(
    "text",
    [
        "41.1579, -8.6291",
        "41,1579 -8,6291",
        "38.7223 N 9.1393 W",
        "41°09'28.4\"N 8°37'44.8\"W",
        "Coordenadas ETRS89/PT-TM06: M = -45123,45 P = 165432,10",
        "32.6669, -16.9241",  # Madeira
    ],
)
def test_gps_is_detected(text: str) -> None:
    found = kinds(text)
    assert found and all(k == "gps" for k, _ in found)


def test_gps_outside_portugal_or_reserved_is_ignored() -> None:
    assert detect("48.8566, 2.3522") == []  # Paris
    assert detect("0.0001, -0.0002") == []
    assert detect("0°00'01\"N 0°00'02\"W") == []


def test_portugal_boxes() -> None:
    assert in_portugal(41.15, -8.62)
    assert in_portugal(37.74, -25.67)  # Azores
    assert not in_portugal(40.4, -3.7)  # Madrid


# ---------------------------------------------------------------- DGEG / OET


@pytest.mark.parametrize(
    "text",
    [
        "OET n.º 15678",
        "inscrito na DGEG com o n.º 4321",
        "membro n.º 12 345 da Ordem dos Engenheiros",
        "Ordem dos Engenheiros Técnicos, cédula profissional 98765",
    ],
)
def test_dgeg_oet_is_detected(text: str) -> None:
    assert "dgeg_oet" in [k for k, _ in kinds(text)]


def test_dgeg_year_references_are_not_numbers() -> None:
    assert detect("Guia Técnico das Instalações Elétricas (DGEG, 2019)") == []
    assert detect("Despacho n.º 1/2018 da DGEG") == []


def test_reserved_dgeg_pseudonym_is_ignored() -> None:
    assert detect("OET n.º 000123") == []


# ---------------------------------------------------------------- addresses


@pytest.mark.parametrize(
    "text",
    [
        "Rua das Flores, n.º 12, 3.º Esq.",
        "Avenida da Boavista 1234",
        "RUA DO BREYNER, 85",
        "Travessa de São Victor",
    ],
)
def test_address_is_detected(text: str) -> None:
    assert [k for k, _ in kinds(text)] == ["address"]


@pytest.mark.parametrize("text", ["Rua Exemplo 3", "RUA EXEMPLO 3", "rua exemplo 3"])
def test_reserved_address_is_ignored(text: str) -> None:
    assert detect(text) == []


# ---------------------------------------------------------------- names (heuristic)


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("O técnico, Eng.ª Maria Sousa Ferreira, declara", "Maria Sousa Ferreira"),
        ("Eng.º JOÃO ALMEIDA", "JOÃO ALMEIDA"),
        ("Requerente: João Pedro Almeida", "João Pedro Almeida"),
        ("Desenhou: Rui Costa", "Rui Costa"),
    ],
)
def test_heuristic_names(text: str, name: str) -> None:
    found = [d for d in detect(text) if d.kind == "name"]
    assert [d.value for d in found] == [name]
    assert all(d.heuristic for d in found)


def test_entities_and_pseudonyms_are_not_names() -> None:
    assert detect("Requerente: Câmara Municipal de Braga") == []
    assert detect("Eng.ª Ana Exemplo") == []


# ---------------------------------------------------------------- user paths


def test_windows_user_path() -> None:
    assert kinds(r"file:///C:\Users\joao.almeida\Desktop\MDJ.docx") == [
        ("user_path", "joao.almeida")
    ]


# ---------------------------------------------------------------- technical text must stay


@pytest.mark.parametrize(
    "text",
    [
        "Potência a alimentar: 34,5 kVA; potência instalada 41,40 kVA",
        "Fios H07V-U e H07V-K, cabos XZ1(frt,zh) e RZ1-K (AS)",
        "Portaria n.º 949-A/2006, Decreto-Lei n.º 96/2017, Despacho n.º 1/2018",
        "NP EN 60529 · NP EN 50102 · EN 50086-2-4 · HD 602 · DMA-C65-210/N",
        "Tomadas 16A-250V, grau de proteção IP65 IK08, 2 x 1,5 mm²",
        "Artigo 5.3.2 · capítulo 2.01.03.04.05 · 24 de setembro de 2026",
        "I2 = 504 A; 1,45·Iz = 503,4 A; queda de tensão 2,87 %",
        "CPE PT 0002 0000 1234 5678 AB",
        "Tensão 230/400 V, 50 Hz, PdC 6 kA, 3% iluminação e 5% outros usos",
        "Caminho de cabos em aço galvanizado",
        "Corrente contínua CC 24 V",
    ],
)
def test_technical_text_is_not_personal_data(text: str) -> None:
    assert detect(text) == []


# ---------------------------------------------------------------- folding


def test_fold_maps_back_to_original() -> None:
    text = "Eng.ª  JOÃO_Almeida"
    folded, index = fold(text)
    assert folded == "eng.a joao almeida"
    start = folded.index("joao")
    s, e = original_span(index, start, start + len("joao almeida"))
    assert text[s:e] == "JOÃO_Almeida"
