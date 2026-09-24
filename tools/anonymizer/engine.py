"""Text-level anonymization: known values (seeds) first, then pattern detectors.

The same engine also scans output text for residual personal data (verification).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from anonymizer.detectors import detect, detect_emails, is_pseudonym_name
from anonymizer.pseudonyms import PseudonymMap, normalize, render
from anonymizer.textnorm import fold, fold_simple, original_span

_CONNECTORS = {"de", "da", "do", "das", "dos", "e"}
# Numeric seeds shorter than this are only replaced where they were harvested or where
# a pattern with context finds them: "4321" alone is too common in technical text.
MIN_GLOBAL_DIGITS = 6
_DIGIT_KINDS = {"nif", "phone", "cc", "postal_code", "dgeg_oet"}
_LITERAL_KINDS = {"email", "address", "gps", "user_path"}
_SEPARATOR = "[ .\\u00a0-]?"


@dataclass(frozen=True)
class Seed:
    """A personal datum known in advance (fixed cells, form tables or overrides)."""

    kind: str
    value: str
    # Local seeds (short numbers such as DGEG/OET) are replaced only in their own file.
    local: bool = False


@dataclass(frozen=True)
class Replacement:
    kind: str
    start: int
    end: int
    original: str
    pseudonym: str
    source: str  # "seed" | "pattern" | "heuristic"


@dataclass(frozen=True)
class Residual:
    kind: str
    severity: str  # "error" | "warning"
    value: str
    heuristic: bool = False


@dataclass
class Allowlist:
    """False positives confirmed by a person, as (kind, folded value) pairs."""

    entries: set[tuple[str, str]] = field(default_factory=set)

    def allows(self, kind: str, value: str) -> bool:
        return (kind, fold_simple(value)) in self.entries

    @classmethod
    def from_items(cls, items: Iterable[tuple[str, str]]) -> "Allowlist":
        return cls({(k, fold_simple(v)) for k, v in items})


def name_variants(folded_name: str) -> set[str]:
    """Folded variants of a folded full name: full, first+last, first+two last, initial."""
    significant = [t for t in folded_name.split() if t not in _CONNECTORS]
    variants = {folded_name}
    if len(significant) >= 2:
        first, last = significant[0], significant[-1]
        variants |= {f"{first} {last}", f"{first[0]}. {last}", " ".join(significant)}
        if len(significant) >= 3:
            variants.add(f"{first} {significant[-2]} {last}")
    return variants


def _char_pattern(key: str) -> str:
    parts = [f"[{c.upper()}{c.lower()}]" if c.isalpha() else re.escape(c) for c in key]
    return r"(?<![0-9A-Za-z])" + _SEPARATOR.join(parts) + r"(?![0-9A-Za-z])"


@dataclass
class _Matchers:
    names: re.Pattern[str] | None
    literals: re.Pattern[str] | None
    digits: re.Pattern[str] | None
    digit_keys: list[tuple[str, str]]  # group index -> (kind, key)


def _alternation(options: Iterable[str], before: str, after: str) -> re.Pattern[str] | None:
    ordered = sorted(set(options), key=len, reverse=True)
    if not ordered:
        return None
    return re.compile(before + "(?:" + "|".join(map(re.escape, ordered)) + ")" + after)


class TextAnonymizer:
    def __init__(
        self,
        mapping: PseudonymMap,
        seeds: Iterable[Seed] = (),
        allowlist: Allowlist | None = None,
    ) -> None:
        self.mapping = mapping
        self.allowlist = allowlist or Allowlist()
        # folded variant -> folded full name ("" when two people share the variant)
        self._name_variants: dict[str, str] = {}
        self._digit_seeds: dict[str, str] = {}  # normalized key -> kind
        self._literal_seeds: dict[str, tuple[str, str]] = {}  # folded literal -> (kind, key)
        self._matchers: _Matchers | None = None
        # Longer names first, so that "Maria Ferreira" becomes an alias of "Maria Sousa Ferreira".
        for seed in sorted(seeds, key=lambda s: -len(s.value.split()) if s.kind == "name" else 0):
            self.add_seed(seed)

    @classmethod
    def for_verification(
        cls, mapping: PseudonymMap, allowlist: Allowlist | None = None
    ) -> "TextAnonymizer":
        """Engine whose seeds are every real value in the table (all projects)."""
        engine = cls(mapping, allowlist=allowlist)
        for kind, keys in mapping.entries.items():
            for key in keys:
                engine._add_key(kind, key)
        return engine

    # ------------------------------------------------------------ seeds

    def add_seed(self, seed: Seed) -> None:
        if not seed.value.strip():
            return
        key = normalize(seed.kind, seed.value)
        owner = self._name_variants.get(key) if seed.kind == "name" else None
        names = self.mapping.entries.setdefault("name", {})
        if owner and owner != key and key not in names:
            # A shorter form of a known name is the same person: same pseudonym.
            names[key] = names[owner]
        self.mapping.number(seed.kind, seed.value)
        # A local seed added here still only matches when long enough; its own file gets
        # it through with_local_seeds().
        self._add_key(seed.kind, key)

    def with_local_seeds(self, seeds: Iterable[Seed]) -> "TextAnonymizer":
        """Copy of this engine that also replaces the given file-local seeds."""
        clone = TextAnonymizer(self.mapping, allowlist=self.allowlist)
        clone._name_variants = dict(self._name_variants)
        clone._digit_seeds = dict(self._digit_seeds)
        clone._literal_seeds = dict(self._literal_seeds)
        for seed in seeds:
            if seed.value.strip():
                self.mapping.number(seed.kind, seed.value)
                clone._add_key(seed.kind, normalize(seed.kind, seed.value), force=True)
        return clone

    def _add_key(self, kind: str, key: str, force: bool = False) -> None:
        if kind == "name":
            if len(key.split()) < 2:
                return
            for variant in name_variants(key):
                owner = self._name_variants.get(variant)
                if owner is None or variant == key:
                    self._name_variants[variant] = key
                elif owner and owner != key:
                    if owner in name_variants(key):
                        self._name_variants[variant] = key
                    elif key not in name_variants(owner):
                        self._name_variants[variant] = ""  # two different people
        elif kind in _DIGIT_KINDS:
            if len(re.sub(r"[^0-9]", "", key)) >= (3 if force else MIN_GLOBAL_DIGITS):
                self._digit_seeds[key] = kind
        elif kind in _LITERAL_KINDS and len(key) >= 4:
            self._literal_seeds[fold_simple(key)] = (kind, key)
        self._matchers = None

    def _get_matchers(self) -> _Matchers:
        if self._matchers is None:
            digit_keys = sorted(self._digit_seeds.items(), key=lambda kv: -len(kv[0]))
            self._matchers = _Matchers(
                names=_alternation(
                    (v for v, owner in self._name_variants.items() if owner),
                    r"(?<![0-9a-z])",
                    r"(?![0-9a-z])",
                ),
                literals=_alternation(self._literal_seeds, r"(?<![0-9a-z@.])", r"(?![0-9a-z])"),
                digits=re.compile(
                    "|".join(f"(?P<d{i}>{_char_pattern(k)})" for i, (k, _) in enumerate(digit_keys))
                )
                if digit_keys
                else None,
                digit_keys=[(kind, key) for key, kind in digit_keys],
            )
        return self._matchers

    def _seed_spans(self, text: str) -> list[tuple[int, int, str, str]]:
        """(start, end, kind, key) of every known value in text."""
        m = self._get_matchers()
        spans: list[tuple[int, int, str, str]] = []
        if m.names or m.literals:
            folded, index = fold(text)
            if m.names:
                for hit in m.names.finditer(folded):
                    s, e = original_span(index, hit.start(), hit.end())
                    spans.append((s, e, "name", self._name_variants[hit.group(0)]))
            if m.literals:
                for hit in m.literals.finditer(folded):
                    s, e = original_span(index, hit.start(), hit.end())
                    kind, key = self._literal_seeds[hit.group(0)]
                    spans.append((s, e, kind, key))
        if m.digits:
            for hit in m.digits.finditer(text):
                assert hit.lastgroup is not None
                kind, key = m.digit_keys[int(hit.lastgroup[1:])]
                spans.append((hit.start(), hit.end(), kind, key))
        return [s for s in spans if s[1] > s[0]]

    # ------------------------------------------------------------ anonymize

    def anonymize(self, text: str) -> tuple[str, list[Replacement]]:
        """Replace every personal datum in text. Returns the new text and what was replaced."""
        if not text or not text.strip():
            return text, []
        chosen: list[Replacement] = []

        def free(s: int, e: int) -> bool:
            return all(e <= r.start or s >= r.end for r in chosen)

        # Longest known value first at each position.
        for s, e, kind, key in sorted(self._seed_spans(text), key=lambda x: (x[0], x[0] - x[1])):
            if free(s, e):
                original = text[s:e]
                n = self.mapping.entries[kind][key]
                chosen.append(Replacement(kind, s, e, original, render(kind, original, n), "seed"))
        for d in detect(text):
            if not free(d.start, d.end) or self.allowlist.allows(d.kind, d.value):
                continue
            if d.kind == "name":
                self.add_seed(Seed("name", d.value))
            source = "heuristic" if d.heuristic else "pattern"
            pseudonym = self.mapping.pseudonym(d.kind, d.value)
            chosen.append(Replacement(d.kind, d.start, d.end, d.value, pseudonym, source))
        if not chosen:
            return text, []
        chosen.sort(key=lambda r: r.start)
        out: list[str] = []
        last = 0
        for r in chosen:
            out += [text[last : r.start], r.pseudonym]
            last = r.end
        out.append(text[last:])
        return "".join(out), chosen

    def replace_value(self, kind: str, value: str) -> str:
        """Pseudonym for a whole value whose kind is known (e.g. a fixed cell)."""
        return self.mapping.pseudonym(kind, value)

    # ------------------------------------------------------------ verification

    def residuals(self, text: str) -> list[Residual]:
        """Personal data still present in already anonymized text."""
        if not text or not text.strip():
            return []
        found = [Residual(kind, "error", text[s:e]) for s, e, kind, _ in self._seed_spans(text)]
        for d in detect(text):
            if self.allowlist.allows(d.kind, d.value):
                continue
            if not d.heuristic:
                found.append(Residual(d.kind, "error", d.value))
            elif not is_pseudonym_name(d.value):
                found.append(Residual(d.kind, "warning", d.value, heuristic=True))
        return found

    def binary_hits(self, data: bytes) -> list[str]:
        """Kinds of known values (and emails) found in binary data, in 8- and 16-bit text."""
        kinds: list[str] = []
        for text in (
            data.decode("latin-1"),
            data.decode("utf-16-le", "ignore"),
            data[1:].decode("utf-16-le", "ignore"),
        ):
            kinds += [kind for _, _, kind, _ in self._seed_spans(text)]
            kinds += ["email" for _ in detect_emails(text)]
        return kinds
