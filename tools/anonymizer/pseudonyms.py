"""Consistent, injective pseudonyms with reserved formats (SPEC 12.2).

The same real value always gets the same pseudonym, across files and projects, and two
different real values never share one (so the C3/C7 inconsistencies survive anonymization).
The table holds real values: it lives in data/private/ only.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from anonymizer.detectors import (
    PSEUDO_FIRST_NAMES,
    PSEUDO_SURNAMES,
    PSEUDO_USER,
    nif_check_digit,
)
from anonymizer.textnorm import digits_only, fold_simple

MAP_VERSION = 1


def normalize(kind: str, value: str) -> str:
    """Key under which a real value is stored: equal keys mean the same real datum."""
    if kind in {"nif", "postal_code", "dgeg_oet"}:
        return digits_only(value)
    if kind == "phone":
        digits = digits_only(value)
        return digits[-9:] if len(digits) > 9 else digits
    if kind == "cc":
        return re.sub(r"[^0-9A-Z]", "", value.upper())
    if kind in {"email", "user_path"}:
        return value.strip().casefold()
    if kind == "gps":
        return fold_simple(value).replace(" ", "")
    return fold_simple(value)


def _format_digits(template: str, digits: str) -> str:
    """Put digits into the template's digit positions, keeping its separators."""
    if len(digits_only(template)) != len(digits):
        return digits
    it = iter(digits)
    return "".join(next(it) if c in "0123456789" else c for c in template)


def _apply_case(template: str, text: str) -> str:
    letters = [c for c in template if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return text.upper()
    if letters and all(c.islower() for c in letters):
        return text.lower()
    return text


class PseudonymMap:
    def __init__(
        self,
        entries: dict[str, dict[str, int]] | None = None,
        counters: dict[str, int] | None = None,
    ) -> None:
        # kind -> normalized real value -> sequence number of its pseudonym
        self.entries: dict[str, dict[str, int]] = entries or {}
        self.counters: dict[str, int] = counters or {}

    # ------------------------------------------------------------ persistence

    @classmethod
    def load(cls, path: Path) -> "PseudonymMap":
        if not path.exists():
            return cls()
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != MAP_VERSION:
            raise ValueError("unsupported correspondence table version")
        return cls(entries=data["entries"], counters=data["counters"])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": MAP_VERSION, "entries": self.entries, "counters": self.counters}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
        os.replace(tmp, path)

    # ------------------------------------------------------------ allocation

    def number(self, kind: str, value: str) -> int:
        key = normalize(kind, value)
        table = self.entries.setdefault(kind, {})
        if key not in table:
            self.counters[kind] = self.counters.get(kind, 0) + 1
            table[key] = self.counters[kind]
        return table[key]

    def keys(self, kind: str) -> list[str]:
        return list(self.entries.get(kind, {}))

    def pseudonym(self, kind: str, value: str) -> str:
        """Pseudonym for value, formatted like value (separators, prefix, case)."""
        return render(kind, value, self.number(kind, value))


def render(kind: str, value: str, n: int) -> str:
    """Pseudonym number n written in the style of value."""
    return _RENDERERS.get(kind, _render_default)(value, n)


# ---------------------------------------------------------------- renderers


def _render_nif(value: str, n: int) -> str:
    if n > 999:
        raise ValueError("too many NIF pseudonyms")
    first8 = f"99999{n:03d}"
    # Deliberately invalid check digit: a pseudonym can never be a real NIF.
    digits = first8 + str((nif_check_digit(first8) + 1) % 10)
    return _format_digits(value.strip(), digits)


def _render_phone(value: str, n: int) -> str:
    m = re.match(r"^(\s*(?:\+|00)351[ .\u00a0]?)?(.*)$", value, re.S)
    assert m is not None
    prefix, national = m.group(1) or "", m.group(2)
    nat_digits = digits_only(national)
    lead = nat_digits[0] if nat_digits[:1] in {"2", "9"} else "9"
    return prefix + _format_digits(national, f"{lead}0000{n:04d}")


def _render_cc(value: str, n: int) -> str:
    digits = iter(f"00000{n:03d}0{n % 10}")
    letters = iter("ZZ")
    out = []
    for c in value:
        if c in "0123456789":
            out.append(next(digits, "0"))
        elif c.isalpha():
            out.append(next(letters, "Z"))
        else:
            out.append(c)
    return "".join(out)


def _render_email(value: str, n: int) -> str:
    return f"pessoa{n:03d}@example.com"


def _render_postal(value: str, n: int) -> str:
    return f"0000-{n:03d}"


def _render_dgeg(value: str, n: int) -> str:
    width = max(len(digits_only(value)), len(str(n)) + 1)
    digits = str(n).rjust(width, "0")
    return _format_digits(value, digits)


def _render_gps(value: str, n: int) -> str:
    def number(m: re.Match[str]) -> str:
        sign, _, sep, frac = m.group(1), m.group(2), m.group(3), m.group(4)
        if not frac:
            return f"{sign}0"
        return f"{sign}0{sep}{str(n).rjust(len(frac), '0')[-len(frac) :]}"

    return re.sub(r"([-+]?)(\d+)(?:([.,])(\d+))?", number, value)


def _render_address(value: str, n: int) -> str:
    return _apply_case(value, f"Rua Exemplo {n}")


def _render_user(value: str, n: int) -> str:
    return f"{PSEUDO_USER}{n:02d}"


def pseudo_name_parts(n: int) -> list[str]:
    first = PSEUDO_FIRST_NAMES[(n - 1) % len(PSEUDO_FIRST_NAMES)]
    block = (n - 1) // len(PSEUDO_FIRST_NAMES)
    surnames = [PSEUDO_SURNAMES[block % len(PSEUDO_SURNAMES)]]
    if block >= len(PSEUDO_SURNAMES):
        surnames.insert(0, PSEUDO_SURNAMES[(block // len(PSEUDO_SURNAMES)) % len(PSEUDO_SURNAMES)])
    return [first, *surnames]


def _render_name(value: str, n: int) -> str:
    parts = pseudo_name_parts(n)
    tokens = value.split()
    initial = bool(tokens) and bool(re.fullmatch(r"\w\.?", tokens[0]))
    text = f"{parts[0][0]}. {' '.join(parts[1:])}" if initial else " ".join(parts)
    return _apply_case(value, text)


def _render_default(value: str, n: int) -> str:
    return f"[DADO {n}]"


_RENDERERS = {
    "nif": _render_nif,
    "phone": _render_phone,
    "cc": _render_cc,
    "email": _render_email,
    "postal_code": _render_postal,
    "dgeg_oet": _render_dgeg,
    "gps": _render_gps,
    "address": _render_address,
    "user_path": _render_user,
    "name": _render_name,
}
