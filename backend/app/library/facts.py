"""Values of a reference project that a block must never keep, each with its key (Phase 3).

- From the ficha-base: the identification keys (id.*) and the powers and voltage, only where
  the text writes them with their unit ("34,5 kVA"). The DGEG list values ("Habitação", "Nova")
  are ordinary words in the text and drive activation rules instead.
- From the cover, by its labels: requerente, localização, código postal and concelho, obra.
- From the signature: local, data and the technician (name, title, CC, OET, verification code).
  doc.local and doc.data only replace text inside the signature.

Keys doc.* and tec.* are not ficha keys: Phase 4 fills them from the document and the profile of
the technician (doc.data stays empty, P8).
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.ingest.detect import fold
from app.ingest.keys import KEYS

UNITS = {
    "ele.potencia_alimentar_kva": "kVA",
    "ele.potencia_instalada_kva": "kVA",
    "ele.potencia_existente_kva": "kVA",
    "ele.tensao_resp_kv": "kV",
}
DOC_KEYS = {
    "doc.local": "Local (assinatura)",
    "doc.data": "Data (assinatura)",
    "tec.nome": "Nome do técnico",
    "tec.titulo": "Título profissional do técnico",
    "tec.cc": "Cartão de cidadão do técnico",
    "tec.oet": "N.º de membro OET do técnico",
    "tec.codigo_verificacao": "Código de verificação das competências",
    "tec.email": "Email do técnico",
    "tec.telefone": "Telefone do técnico",
}
MIN_TEXT = 4  # shorter strings are too common to be told apart from ordinary text


@dataclass(frozen=True)
class Fact:
    key: str
    value: str
    pattern: re.Pattern[str]
    scope: str = "document"  # document | signature

    @property
    def placeholder(self) -> str:
        return "{{v:" + self.key + "}}"


def number_text(value: Any) -> str:
    """34.5 -> "34,5"; 180.0 -> "180" (as the documents write them)."""
    number = Decimal(str(value)).normalize()
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def text_fact(key: str, value: str, scope: str = "document") -> Fact | None:
    value = " ".join(str(value).split()).strip(" ,;:")
    if len(value) < MIN_TEXT and key not in ("tec.cc", "tec.oet"):
        return None
    words = [re.escape(w) for w in value.split()]
    pattern = re.compile(r"(?<!\w)" + r"\s*".join(words) + r"(?!\w)", re.I)
    return Fact(key, value, pattern, scope)


def ficha_facts(values: dict[str, Any]) -> list[Fact]:
    facts: list[Fact] = []
    # ties are broken by this order: the power compared between sources (Phase 1) first, then
    # the order of KEYS (concelho before distrito)
    first = "ele.potencia_alimentar_kva"
    for key in [first, *(k for k in KEYS if k != first)]:
        value = values.get(key)
        if value in (None, ""):
            continue
        if key in UNITS:
            number = number_text(value)
            digits = re.escape(number).replace(",", "[,.]")
            unit = UNITS[key]
            pattern = re.compile(rf"(?<![\d,.])({digits})(?:[,.]0+)?(?=\s*{unit}\b)", re.I)
            facts.append(Fact(key, f"{number} {unit}", pattern))
        elif key.startswith("id.") and isinstance(value, str):
            fact = text_fact(key, value)
            if fact:
                facts.append(fact)
    return facts


_COVER = re.compile(r"^\s*(REQUERENTE|LOCALIZA[CÇ][AÃ]O|OBRA)\s*:?\s*(.+?)\s*$", re.I)
_POSTAL_LINE = re.compile(r"^\s*(\d{4}\s?[-\u2013]\s?\d{3})\s*,?\s*(.*?)\s*$")
_COVER_KEYS = {"requerente": "id.requerente.nome", "localizacao": "id.local.rua",
               "obra": "id.obra.designacao"}  # fmt: skip

_SIGN_DATE = re.compile(r"^\s*([^,\d]+?),\s*(\w+\s+de\s+\d{4})\s*\.?\s*$")
_SIGN_NAME = re.compile(r"^\s*([^,\d]+?),\s*(eng\w*\.?\s.*?)\s*$", re.I)
_SIGN_FIELDS = [
    (re.compile(r"^\s*C\.?\s?C\.?\s*(?:n\.?º)?\s*:?\s*(.+?)\s*$", re.I), "tec.cc"),
    (re.compile(r"^\s*Membro\s+(?:da\s+)?OET\s*:?\s*(?:n\.?º)?\s*(.+?)\s*$", re.I), "tec.oet"),
    (re.compile(r"verifica[cç][aã]o[^:]*:\s*(.+?)\s*$", re.I), "tec.codigo_verificacao"),
    (re.compile(r"^\s*(?:email|e-mail)\s*:?\s*(\S+@\S+)\s*$", re.I), "tec.email"),
    (re.compile(r"^\s*(?:tel\.?|telefone|telem[oó]vel)\s*:?\s*([+\d][\d\s]{7,})\s*$", re.I),
     "tec.telefone"),
]  # fmt: skip


def cover_facts(lines: list[str]) -> list[Fact]:
    facts: list[Fact] = []
    after_location = False
    for line in lines:
        m = _COVER.match(line)
        if m:
            key = _COVER_KEYS[re.sub(r"[^a-z]", "", fold(m.group(1)))]
            fact = text_fact(key, m.group(2))
            if fact:
                facts.append(fact)
            after_location = key == "id.local.rua"
            continue
        if after_location and (p := _POSTAL_LINE.match(line)):
            facts += [f for f in (text_fact("id.local.cp", p.group(1)),
                                  text_fact("id.local.concelho", p.group(2))) if f]  # fmt: skip
        after_location = False
    return facts


def signature_facts(lines: list[str]) -> list[Fact]:
    facts: list[Fact] = []
    for line in lines:
        if m := _SIGN_DATE.match(line):
            facts += [f for f in (text_fact("doc.local", m.group(1), "signature"),
                                  text_fact("doc.data", m.group(2), "signature")) if f]  # fmt: skip
        elif m := _SIGN_NAME.match(line):
            name = text_fact("tec.nome", m.group(1))
            title = text_fact("tec.titulo", m.group(2), "signature")
            facts += [f for f in (name, title) if f]
        else:
            for pattern, key in _SIGN_FIELDS:
                if m := pattern.search(line):
                    fact = text_fact(key, m.group(1))
                    if fact:
                        facts.append(fact)
                    break
    return facts
