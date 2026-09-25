"""Cable and wire designations as they are written in the project files (SPEC 7.5, COE-06).

A designation is split into its family (the cable type, e.g. "XZ1(frt,zh)", "RZ1-K (AS)",
"H07V-U") and its geometry ("5G10", "4x16", "4x1x185"). The dictionary is kept per family; each
occurrence keeps the text exactly as it appears and where. Writing variants (spaces, "mm2"/"mm²",
typographic hyphens, "4(1x185)") are the same designation. Equivalences between families are only
ever proposed, with evidence, and never between a rigid (-U, -R) and a flexible (-K, -F) type:
the curator decides (SPEC 7.5).
"""

import re
from dataclasses import dataclass

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
_FIRE = r"\s?\((?:AS|fr[ts]\s?,\s?zh)\)"
# Order matters: longer and more specific families first.
_FAMILIES = (
    r"H0[3579]V{1,2}-[UKRF]",
    r"H0[57]RN-F",
    r"F?[XRS]Z1(?:-K)?" + _FIRE,
    r"F?[XRS]Z1(?:-K)?",
    r"LSVAV",
    r"XAV",
    r"RVFV",
    r"RV-?K",
    r"VV-F",
    r"XV-[RU]",
    r"LXV",
    r"XV",
    r"VAV",
)
_FAMILY = re.compile(r"(?<![\w-])(" + "|".join(_FAMILIES) + r")(?![\w])", re.I)
_SECTION = r"(\d+(?:[.,]\d+)?)"
# Right after the family: "5G10mm2", "4x16", "4x1x185mm²", "4(1x185)", "- 10mm²", "1G16mm²".
_GEOMETRY = re.compile(
    r"^\s*-?\s*(?:"
    r"(?P<n>\d+)\s*\(\s*1\s*[xX]\s*" + _SECTION + r"\s*\)"
    r"|(?P<c>\d+)\s*(?P<sep>[xXG])\s*(?:1\s*[xX]\s*(?P<one>))?"
    + _SECTION.replace("(", "(?P<s>", 1)
    + r"|"
    + _SECTION.replace("(", "(?P<only>", 1)
    + r"\s*m?m[2²]"
    r")"
)
# Cores written before the family: "3x H07V-U 10mm²".
_CORES_BEFORE = re.compile(r"(\d+)\s*[xX]\s*$")
# Families that are only accepted with a geometry: short letters that also appear in plain text.
_NEEDS_GEOMETRY = {"XV", "VAV", "LXV"}


@dataclass(frozen=True)
class Designation:
    raw: str  # the text as it appears (normalized hyphens and spaces only)
    family: str  # canonical family, e.g. "XZ1(frt,zh)"
    geometry: str | None  # e.g. "5G10", "4x1x185", "1x10"


def canonical_family(text: str) -> str:
    """ "rz1-k (as)" → "RZ1-K (AS)"; "XZ1 (frt, zh)" → "XZ1(frt,zh)"; "rvk" → "RV-K"."""
    t = " ".join(text.translate(_DASHES).split())
    fire = re.search(r"\((AS|fr[ts]\s?,\s?zh)\)", t, re.I)
    base = re.sub(r"\s?\(.*\)", "", t).upper()
    if base == "RVK":
        base = "RV-K"
    if not fire:
        return base
    mark = fire.group(1)
    if mark.upper() == "AS":
        return f"{base} (AS)"  # as written in the TUU Tabela
    return f"{base}({mark.replace(' ', '').lower()})"


def _section(text: str) -> str:
    return text.replace(".", ",")


def _geometry(after: str, before: str) -> str | None:
    m = _GEOMETRY.match(after)
    cores = _CORES_BEFORE.search(before)
    if not m:
        return None
    if m.group("n"):
        return f"{m.group('n')}x1x{_section(m.group(2))}"
    if m.group("c"):
        sep = "G" if m.group("sep") in "G" else "x"
        middle = "1x" if m.group("one") is not None else ""
        return f"{m.group('c')}{sep}{middle}{_section(m.group('s'))}"
    if m.group("only"):
        n = cores.group(1) if cores else "1"
        return f"{n}x{_section(m.group('only'))}"
    return None


def find(text: str) -> list[Designation]:
    """Every cable or wire designation in a text."""
    clean = " ".join(str(text).translate(_DASHES).split())
    out: list[Designation] = []
    for m in _FAMILY.finditer(clean):
        family = canonical_family(m.group(1))
        before = clean[max(0, m.start() - 8) : m.start()]
        geometry = _geometry(clean[m.end() : m.end() + 30], before)
        if family.split("(")[0].strip() in _NEEDS_GEOMETRY and geometry is None:
            near = clean[max(0, m.start() - 20) : m.end() + 20]
            others = [f for f in _FAMILY.findall(near) if canonical_family(f) != family]
            if not others and not re.search(r"\bcabos?\b", near, re.I):
                continue  # "XV" alone is not a cable ("século XV")
        start, end = m.start(), m.end()
        cores = _CORES_BEFORE.search(before)
        if cores and geometry:
            start = m.start() - (len(before) - cores.start())
        if geometry:
            g = _GEOMETRY.match(clean[m.end() : m.end() + 30])
            end = m.end() + (g.end() if g else 0)
            tail = re.match(r"\s*m?m[2²]", clean[end:])
            end += tail.end() if tail else 0
        out.append(Designation(clean[start:end].strip(), family, geometry))
    return out


def kind(family: str) -> str:
    """ "fio" for single-core building wires (H0xV-…), "cabo" otherwise."""
    return "fio" if re.match(r"H0\dV-", family) else "cabo"


def flexible(family: str) -> bool | None:
    """True for -K/-F (flexible), False for -U/-R (rigid), None when the name does not say."""
    base = family.split("(")[0].strip().upper()
    if re.search(r"-[KF]\b", base) or base in {"RV-K", "RVFV"}:
        return True
    if re.search(r"-[UR]\b", base):
        return False
    return None


def may_be_equivalent(a: str, b: str) -> bool:
    """Never propose a rigid and a flexible type (e.g. H07V-U and H07V-K) as equivalent."""
    if a == b:
        return False
    fa, fb = flexible(a), flexible(b)
    if fa is not None and fb is not None and fa != fb:
        return False
    return kind(a) == kind(b)
