"""Pattern detectors for Portuguese personal data (SPEC 12.2).

Every detector returns spans; the matched value stays in memory and is never printed.
Pseudonyms use reserved formats (see is_reserved) so that a fixtures-only check can
recognise them without the correspondence table.
"""

import re
from dataclasses import dataclass

from anonymizer.textnorm import digits_only

KINDS: tuple[str, ...] = (
    "name",
    "nif",
    "cc",
    "phone",
    "email",
    "postal_code",
    "gps",
    "dgeg_oet",
    "address",
    "user_path",
)

LABELS_PT: dict[str, str] = {
    "name": "nome",
    "nif": "NIF",
    "cc": "CC/BI",
    "phone": "telefone",
    "email": "email",
    "postal_code": "código postal",
    "gps": "coordenadas",
    "dgeg_oet": "n.º DGEG/OET",
    "address": "morada",
    "user_path": "caminho de utilizador",
}

# Names used for pseudonyms. Never real people: the surnames are ordinary words.
PSEUDO_FIRST_NAMES: tuple[str, ...] = (
    "Ana", "Bruno", "Carla", "Daniel", "Eva", "Filipe", "Gabriela", "Hugo", "Inês", "Jorge",
    "Luísa", "Mário", "Nuno", "Olga", "Paulo", "Rita", "Sérgio", "Teresa", "Vasco", "Zita",
)  # fmt: skip
PSEUDO_SURNAMES: tuple[str, ...] = ("Exemplo", "Fictício", "Imaginário", "Suposto", "Teórico")
PSEUDO_USER = "utilizador"


@dataclass(frozen=True)
class Detection:
    kind: str
    start: int
    end: int
    value: str
    heuristic: bool = False


# ---------------------------------------------------------------- NIF and 9-digit numbers


def nif_check_digit(first8: str) -> int:
    total = sum(int(d) * (9 - i) for i, d in enumerate(first8))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def nif_valid(digits: str) -> bool:
    return (
        len(digits) == 9
        and digits.isdigit()
        and digits[0] != "0"
        and nif_check_digit(digits[:8]) == int(digits[8])
    )


def _reserved_nine(digits: str) -> bool:
    return (digits.startswith("99999") and not nif_valid(digits)) or bool(
        re.fullmatch(r"[29]0000\d{4}", digits)
    )


_S = r"[ .\u00a0]"
# Only the groupings people actually write (912 345 678, 22 123 45 67, 21 1234567\u2026), so
# that dotted article codes like 2.01.03.04.05 are not mistaken for phone numbers.
_NINE_GROUPS = (
    rf"(?:\d{{3}}{_S}\d{{3}}{_S}\d{{3}}|\d{{2}}{_S}\d{{3}}{_S}\d{{2}}{_S}\d{{2}}|"
    rf"\d{{3}}{_S}\d{{2}}{_S}\d{{2}}{_S}\d{{2}}|\d{{2}}{_S}\d{{3}}{_S}\d{{4}}|"
    rf"\d{{2}}{_S}\d{{7}}|\d{{3}}{_S}\d{{6}}|\d{{9}})"
)
_NINE = re.compile(
    rf"(?<![\w.,/+\-])(?P<prefix>(?:\+|00)351{_S}?)?(?P<num>{_NINE_GROUPS})(?![\w]|[.,]\d)"
)
_NIF_CONTEXT = re.compile(
    r"(?i)\b(?:nif|nipc|n\.?\s?i\.?\s?f\.?|contribuinte|identifica[cç][aã]o fiscal)\b[^\d]{0,25}$"
)
_PHONE_CONTEXT = re.compile(
    r"(?i)\b(?:tel|telef|telefone|telem[oó]vel|telm|tlm|tlf|contacto|contato|fax|m[oó]vel|"
    r"phone)\b\.?[^\d]{0,15}$"
)


def _nine_digit(text: str) -> list[Detection]:
    found: list[Detection] = []
    for m in _NINE.finditer(text):
        digits = digits_only(m.group("num"))
        if _reserved_nine(digits):
            continue
        before = text[max(0, m.start() - 40) : m.start()]
        kind: str | None
        if m.group("prefix"):
            kind = "phone"
        elif _NIF_CONTEXT.search(before):
            kind = "nif"
        elif _PHONE_CONTEXT.search(before):
            kind = "phone"
        elif nif_valid(digits):
            kind = "nif"
        elif digits[0] in "29":
            kind = "phone"
        else:
            kind = None
        if kind:
            found.append(Detection(kind, m.start(), m.end(), m.group(0)))
    return found


# ---------------------------------------------------------------- CC / BI

_CC_FULL = re.compile(r"(?<![\w])\d{8}[ -]?\d[ -]?[A-Za-z]{2}\d(?![\w])")
_CC_CONTEXT = re.compile(
    r"(?i)\b(?:c\.?\s?c\.?|cart[aã]o de cidad[aã]o|b\.?\s?i\.?|bilhete de identidade|"
    r"identifica[cç][aã]o civil|documento de identifica[cç][aã]o)(?![\w])"
    r"[^\w]{0,6}(?:n\.?\s?[ºo°]?\.?\s*)?[:\s]*"
    r"(?P<num>\d{7,8}(?:[ -]?\d)?(?:[ -]?[A-Za-z]{2}\d)?)(?![\w])"
)


def _cc(text: str) -> list[Detection]:
    found = [Detection("cc", m.start(), m.end(), m.group(0)) for m in _CC_FULL.finditer(text)]
    for m in _CC_CONTEXT.finditer(text):
        found.append(Detection("cc", m.start("num"), m.end("num"), m.group("num")))
    return [d for d in found if not digits_only(d.value).startswith("00000")]


# ---------------------------------------------------------------- email, postal code

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_POSTAL = re.compile(r"(?<![\w-])\d{4}-\d{3}(?![\w-])")


def _email(text: str) -> list[Detection]:
    return [
        Detection("email", m.start(), m.end(), m.group(0))
        for m in _EMAIL.finditer(text)
        if not m.group(0).casefold().endswith("@example.com")
    ]


def detect_emails(text: str) -> list[Detection]:
    return _email(text)


def _postal(text: str) -> list[Detection]:
    return [
        Detection("postal_code", m.start(), m.end(), m.group(0))
        for m in _POSTAL.finditer(text)
        if not m.group(0).startswith("0000-")
    ]


# ---------------------------------------------------------------- coordinates

_GPS_DECIMAL = re.compile(
    r"(?<![\w.,])(?P<a>[-+]?\d{1,2}[.,]\d{4,})\s*[°º]?\s*(?P<ah>[NSns])?"
    r"(?:\s*[,;/]\s*|\s+)"
    r"(?P<bh0>[EWOewo]\s?)?(?P<b>[-+]?\d{1,3}[.,]\d{4,})\s*[°º]?\s*(?P<bh>[EWOewo])?(?![\w])"
)
_GPS_DMS = re.compile(
    r"(?<![\w])(?:[NSEWOnsewo]\s?)?(?P<deg>\d{1,3})\s?[°º]\s?\d{1,2}\s?['’′]\s?"
    r"\d{1,2}(?:[.,]\d+)?\s?(?:\"|''|”|″)?\s?(?:[NSEWOnsewo](?![\w]))?"
)
_COORD_CONTEXT = re.compile(
    r"(?i)\b(?:coordenadas|gps|etrs\s?89|pt-tm06|wgs\s?84|latitude|longitude)\b"
)
_COORD_NUMBER = re.compile(r"(?<![\w.,])[-+]?\d{1,6}[.,]\d{2,}(?![\w])")

_PT_BOXES = (
    (36.8, 42.3, 6.0, 9.7),  # mainland
    (36.8, 39.8, 24.8, 31.5),  # Azores
    (32.3, 33.2, 16.2, 17.4),  # Madeira
    (29.9, 30.3, 15.8, 16.1),  # Selvagens
)


def _to_float(value: str) -> float:
    return float(value.replace(",", ".").replace("+", ""))


def in_portugal(lat: float, lon: float) -> bool:
    lat, lon = abs(lat), abs(lon)
    return any(a <= lat <= b and c <= lon <= d for a, b, c, d in _PT_BOXES)


def _gps(text: str) -> list[Detection]:
    found: list[Detection] = []
    for m in _GPS_DECIMAL.finditer(text):
        if in_portugal(_to_float(m.group("a")), _to_float(m.group("b"))):
            found.append(Detection("gps", m.start(), m.end(), m.group(0)))
    for m in _GPS_DMS.finditer(text):
        if int(m.group("deg")) != 0:
            found.append(Detection("gps", m.start(), m.end(), m.group(0).rstrip()))
    for ctx in _COORD_CONTEXT.finditer(text):
        window_end = min(len(text), ctx.end() + 80)
        for m in _COORD_NUMBER.finditer(text, ctx.end(), window_end):
            if abs(_to_float(m.group(0))) >= 1:
                found.append(Detection("gps", m.start(), m.end(), m.group(0)))
    return found


# ---------------------------------------------------------------- DGEG / OET numbers

_DGEG_OET = re.compile(
    r"(?:\b(?:DGEG|OET|O\.E\.T\.|OE|O\.E\.)(?![\w])|"
    r"(?i:\b(?:ordem dos engenheiros(?: t[ée]cnicos)?|inscri[çc][ãa]o|membro|licen[çc]a|"
    r"c[ée]dula profissional|alvar[áa]|t[ée]cnico n\.?\s?º)\b))"
    r"(?P<gap>[^\d\n]{0,30}?)(?P<num>\d(?:[ .]?\d){2,6})(?![\d]|[.,]\d|\s?/)"
)
_NUMBER_HINT = re.compile(r"(?i)n\.?\s?[ºo°]|n[uú]mero|:")


def _dgeg_oet(text: str) -> list[Detection]:
    found: list[Detection] = []
    for m in _DGEG_OET.finditer(text):
        digits = digits_only(m.group("num"))
        if digits.startswith("0"):
            continue
        is_year = len(digits) == 4 and 1950 <= int(digits) <= 2099
        if is_year and not _NUMBER_HINT.search(m.group("gap")):
            continue
        found.append(Detection("dgeg_oet", m.start("num"), m.end("num"), m.group("num")))
    return found


# ---------------------------------------------------------------- addresses

_UPPER = "A-ZÁÀÂÃÉÊÍÓÔÕÚÇ"
_STREET = (
    r"(?:Rua|R\.|Avenida|Av\.ª|Avª|Av\.|Travessa|Trav\.|Tv\.|Largo|Lg\.|Praceta|Praça|Pç\.|"
    r"Estrada|Estr\.|Rotunda|Alameda|Beco|Calçada|Urbanização|Urb\.|Lugar|Bairro|Caminho|"
    r"Azinhaga|Viela|Quinta|RUA|AVENIDA|TRAVESSA|LARGO|PRACETA|PRAÇA|ESTRADA|ROTUNDA|"
    r"ALAMEDA|BECO|CALÇADA|URBANIZAÇÃO|LUGAR|BAIRRO|CAMINHO|AZINHAGA|VIELA|QUINTA)"
)
_ADDRESS = re.compile(
    rf"(?<![\w]){_STREET}\s+(?:(?:d[aoe]s?|de)\s+)?"
    rf"(?P<n>[{_UPPER}][\w'’.-]*(?:\s+(?:(?:d[aoe]s?|de|e)\s+)?[{_UPPER}0-9][\w'’.-]*){{0,6}})"
    # house number (never a postal code such as 4100-456)
    r"(?:\s*,?\s*(?:n\.?\s?[ºo°]\.?\s*)?(?!\d{4}-\d{3})\d+[A-Za-z]?(?:\s*/\s*\d+)?(?![\w-]))?"
    r"(?:\s*,?\s*\d+\.?\s?[ºo°]\.?\s*(?:Esq|Dto|Dt|Frt|Fte|Esquerdo|Direito)\.?)?"
)


def _address(text: str) -> list[Detection]:
    return [
        Detection("address", m.start(), m.end(), m.group(0).rstrip(" ,"))
        for m in _ADDRESS.finditer(text)
        # Our own pseudonym, in any case ("RUA EXEMPLO 3" when the original was in capitals).
        if not m.group("n").casefold().startswith("exemplo")
    ]


# ---------------------------------------------------------------- user paths

_USER_PATH = re.compile(
    r"(?i)(?:[a-z]:[\\/]+(?:users|utilizadores|documents and settings)[\\/]+|/(?:users|home)/)"
    r"(?P<u>[^\\/\s\"'<>]+)"
)


def _user_path(text: str) -> list[Detection]:
    return [
        Detection("user_path", m.start("u"), m.end("u"), m.group("u"))
        for m in _USER_PATH.finditer(text)
        if not m.group("u").casefold().startswith(PSEUDO_USER)
        and m.group("u").casefold() not in {"public", "default", "all users"}
    ]


# ---------------------------------------------------------------- names (heuristic)

_HONORIFIC_WORDS = r"(?:Eng|Engª|Engº|Arq|Arqª|Arqº|Sr|Sra|Srª|Dr|Dra|Drª|Exmo|Exma|Prof)"
_CAP = rf"(?!{_HONORIFIC_WORDS}\b)[{_UPPER}][A-Za-zÀ-ÿ'’-]+"
_NAME_SEQ = rf"{_CAP}(?:\s+(?:(?:d[aoe]s?|de|e)\s+)?{_CAP}){{0,5}}"
_HONORIFIC = re.compile(
    r"\b(?:Eng\.?(?:º|ª|o|a)?|Engenheir[oa]|Arq\.?(?:º|ª)?|Arquitet[oa]|Sr\.?(?:ª|a)?|Sra\.|"
    r"Senhora?|Dr\.?(?:ª|a)?|Dra\.|Doutora?|Exm[oa]\.?|Prof\.?(?:ª)?)"
    rf"\.?\s+(?P<n>{_NAME_SEQ})"
)
_LABEL_NAME = re.compile(
    r"(?i:\b(?:requerente|promotor|dono de obra|t[ée]cnico(?: respons[áa]vel)?|projetista|"
    r"autor(?: do projeto)?|desenhou|verificou|aprovou|projetou|coordenador|nome(?: completo)?)"
    r")\s*[:–-]\s*"
    rf"(?P<n>{_NAME_SEQ})"
)
ENTITY_WORDS = re.compile(
    r"(?i)\b(?:c[âa]mara|municipal|munic[íi]pio|junta|freguesia|lda|limitada|sociedade|s\.?a\.?|"
    r"associa[çc][ãa]o|funda[çc][ãa]o|instituto|universidade|escola|agrupamento|miseric[óo]rdia|"
    r"cooperativa|condom[íi]nio|empresa|grupo|constru[çc][õo]es|imobili[áa]ria|servi[çc]os|"
    r"hospital|centro|biblioteca|dire[çc][ãa]o|minist[ée]rio|governo|rep[úu]blica|estado|"
    r"unipessoal|engenharia|projetos|arquitetura|gabinete|tuu)\b"
)


def is_pseudonym_name(name: str) -> bool:
    tokens = [t.strip(".") for t in name.split()]
    pool = {t.casefold() for t in (*PSEUDO_FIRST_NAMES, *PSEUDO_SURNAMES)}
    return bool(tokens) and all(t.casefold() in pool or len(t) == 1 for t in tokens)


def _names(text: str) -> list[Detection]:
    found: list[Detection] = []
    for pattern in (_HONORIFIC, _LABEL_NAME):
        for m in pattern.finditer(text):
            name = m.group("n")
            if ENTITY_WORDS.search(name) or is_pseudonym_name(name):
                continue
            found.append(Detection("name", m.start("n"), m.end("n"), name, heuristic=True))
    return found


# ---------------------------------------------------------------- public API

# Earlier detectors win when spans overlap (an email contains digits, an address a number…).
_DETECTORS = (_email, _user_path, _cc, _gps, _nine_digit, _postal, _dgeg_oet, _address, _names)


def detect(text: str) -> list[Detection]:
    """All pattern detections in text, non-overlapping and sorted by position."""
    taken: list[Detection] = []
    for detector in _DETECTORS:
        for d in detector(text):
            if d.end > d.start and all(d.end <= t.start or d.start >= t.end for t in taken):
                taken.append(d)
    return sorted(taken, key=lambda d: d.start)
