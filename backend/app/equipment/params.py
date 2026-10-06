"""Parameters of equipment, read the same way from the CTE and from the datasheets (Phase 7).

Each parameter has a normalised name (SPEC 7.6), a unit, the way a requirement compares it and a
pattern. Nothing is computed: a value is what the text says (IP55, 25 kA, 590 Wp); "20KW" and
"7,4kW" are the power in kW, never converted. Without the LLM: what a pattern does not read
stays for the curator.

Comparison of a requirement with an offered value:
- `>=class`: protection codes digit by digit (IP55 >= IP44; an X digit is not compared), IK by
  number, Euroclass of cables by rank (B2ca better than Cca);
- `>=` / `<=`: numbers (minimums and maximums);
- `=`: the same number;
- text parameters (dimensions) are information only: never compared.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.ingest.detect import fold

GE, LE, EQ, GE_CLASS, INFO = ">=", "<=", "=", ">=class", "info"
OPERATORS = (GE, LE, EQ, GE_CLASS, INFO)
_NUM = r"(\d+(?:[.,]\d+)?)"
EUROCLASSES = ("A1ca", "A2ca", "B1ca", "B2ca", "Cca", "Dca", "Eca", "Fca")  # best first


@dataclass(frozen=True)
class Param:
    name: str
    label: str  # in Portuguese, for the screens
    unit: str
    operator: str  # how a requirement compares it
    pattern: re.Pattern[str]
    kind: str = "number"  # number | class | text


def _p(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


PARAMS: dict[str, Param] = {p.name: p for p in (
    Param("ip_rating", "Índice de proteção (IP)", "", GE_CLASS,
          _p(r"\bIP\s?([0-6X][0-9X])(?![\d])"), "class"),
    Param("ik_rating", "Resistência ao impacto (IK)", "", GE_CLASS,
          _p(r"\bIK\s?(\d{2})(?!\d)"), "class"),
    Param("icc_ka", "Corrente de curto-circuito", "kA", GE,
          _p(rf"{_NUM}\s?kA\b")),
    Param("power_w", "Potência", "W", EQ,
          _p(rf"(?<![\w,.]){_NUM}\s?W(?![\w])")),
    Param("power_kw", "Potência", "kW", EQ,
          _p(rf"(?<![\w,.]){_NUM}\s?kW(?![\w])")),
    Param("peak_power_wp", "Potência de pico", "Wp", GE,
          re.compile(rf"(?<![\w,.]){_NUM}\s?Wp\b")),  # "1812WP" is a product name
    Param("luminous_flux_lm", "Fluxo luminoso", "lm", GE,
          _p(rf"(?<![\w,.]){_NUM}\s?lm\b")),
    Param("color_temperature_k", "Temperatura de cor", "K", EQ,
          _p(r"(?<![\w,.])(\d{4})\s?K\b")),
    Param("voltage_v", "Tensão", "V", EQ,
          _p(r"(?<![\w,.])(\d{2,4})\s?V(?:\s?(?:AC|DC|ac|dc))?(?![\w])")),
    Param("detection_range_m", "Alcance de deteção", "m", GE,
          _p(rf"(?:dete[cç][aã]o|alcance)\D{{0,25}}?{_NUM}\s?m\b")),
    Param("detection_angle_deg", "Ângulo de deteção", "º", GE,
          _p(r"(?<![\w,.])(\d{2,3})\s?[º°](?!\s?C\b)")),
    Param("efficiency_pct", "Eficiência", "%", GE,
          _p(rf"efici[eê]ncia\D{{0,25}}?{_NUM}\s?%")),
    Param("autonomy_h", "Autonomia", "h", GE,
          _p(r"autonomia\D{0,10}?(\d+(?:[.,]\d+)?|uma)\s?(?:h\b|hora)")),
    Param("cpr_class", "Classe de reação ao fogo (CPR)", "", GE_CLASS,
          _p(r"\b(A1ca|A2ca|B1ca|B2ca|Cca|Dca|Eca|Fca)\b"), "class"),
    Param("dimensions_mm", "Dimensões", "mm", INFO,
          _p(r"(\d+(?:[.,]\d+)?\s?[x\u00d7]\s?\d+(?:[.,]\d+)?(?:\s?[x\u00d7]\s?\d+(?:[.,]\d+)?)?)\s?mm\b"),
          "text"),
)}  # fmt: skip


@dataclass
class Reading:
    name: str
    value: Any  # float, or the code ("IP55", "IK10", "Cca") or the text
    unit: str
    text: str  # what was read, as written
    start: int = 0


def number(text: str) -> float | None:
    if fold(text) == "uma":
        return 1.0
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _value(param: Param, raw: str) -> Any:
    if param.name == "ip_rating":
        return f"IP{raw.upper()}"
    if param.name == "ik_rating":
        return f"IK{raw}"
    if param.name == "cpr_class":
        return next(c for c in EUROCLASSES if c.lower() == raw.lower())
    if param.kind == "text":
        return re.sub(r"\s+", "", raw).replace("\u00d7", "x")
    return number(raw)


def read(text: str) -> Iterator[Reading]:
    """Every parameter a text says, in the order of the text (a name may repeat)."""
    found: list[Reading] = []
    for param in PARAMS.values():
        for m in param.pattern.finditer(text):
            value = _value(param, m.group(1))
            if value is None:
                continue
            found.append(Reading(param.name, value, param.unit, m.group(0).strip(), m.start()))
    yield from sorted(found, key=lambda r: r.start)


def shown(name: str, value: Any) -> str:
    param = PARAMS.get(name)
    if isinstance(value, float):
        text = f"{value:g}".replace(".", ",")
        return f"{text} {param.unit}".strip() if param else text
    return str(value)


def _class_ok(name: str, required: str, offered: str) -> bool | None:
    if name == "cpr_class":
        if required not in EUROCLASSES or offered not in EUROCLASSES:
            return None
        return EUROCLASSES.index(offered) <= EUROCLASSES.index(required)
    if name == "ik_rating":
        return int(offered[2:]) >= int(required[2:])
    pairs = [(r, o) for r, o in zip(required[2:], offered[2:], strict=False) if r != "X"]
    if not pairs or any(o == "X" for _, o in pairs):
        return None  # the code does not say the protection that is required: not comparable
    return all(int(o) >= int(r) for r, o in pairs)


def satisfies(name: str, operator: str, required: Any, offered: Any) -> bool | None:
    """Whether an offered value meets a requirement; None when it cannot be compared."""
    if operator == INFO or required is None or offered is None:
        return None
    if operator == GE_CLASS:
        return _class_ok(name, str(required), str(offered))
    try:
        r, o = float(required), float(offered)
    except (TypeError, ValueError):
        return None
    if operator == GE:
        return o >= r
    if operator == LE:
        return o <= r
    return abs(o - r) < 1e-9


def normalize(name: str, raw: object) -> Any:
    """A value written by a curator, as the patterns would read it; ValueError if it is not."""
    param = PARAMS.get(name)
    if param is None:
        raise ValueError(f"Parâmetro desconhecido: {name}")
    text = str(raw).strip()
    if param.kind == "number":
        value = number(text) if not isinstance(raw, int | float) else float(raw)
        if value is None:
            raise ValueError(f"«{text}» não é um número.")
        return value
    if param.kind == "text":
        return text
    m = param.pattern.search(text) or param.pattern.search(f"{name[:2].upper()}{text}")
    if m is None:
        raise ValueError(f"«{text}» não é um valor de {param.label}.")
    return _value(param, m.group(1))
