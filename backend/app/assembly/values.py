"""Values a section can write, from one confirmed ficha-base revision (Phase 4).

Keys:
- ficha-base keys (SPEC 7.2), from FichaValue;
- circ.<origin_destination>.<field>: a circuit of the Tabela de Cálculo, e.g. circ.qeg_qp_1_1.in_a;
- bom.<code>.<field>: an article of the MQT/LPU, e.g. bom.8_1_1.quantity;
- doc.* and tec.*: the document and the technician (profile, Phase 4 task 6); doc.data is always
  empty (the technician dates the document, P8).

Nothing is computed: a value is written as it is in the ficha-base. Personal values are
resolved here, in the backend, and never leave it except in the document itself.
"""

import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.keys import KEYS
from app.library.docx_blocks import slug
from app.library.facts import number_text
from app.library.preview import label as key_label
from app.library.rules import CIRCUIT_FIELDS
from app.models import BomItem, Circuit, FichaRevision, FichaValue

BOM_FIELDS = ("designation", "unit", "quantity", "code")
EMPTY_BY_DESIGN = {"doc.data"}  # P8: left for the technician
PERSONAL_DOC_KEYS = {"tec.nome", "tec.cc", "tec.oet", "tec.codigo_verificacao", "tec.email",
                     "tec.telefone"}  # fmt: skip


def circuit_slug(c: Circuit) -> str:
    return slug(f"{c.origin or ''} {c.destination or ''}")


def bom_slug(item: BomItem) -> str:
    return slug(item.code or f"linha {item.row_index}")


@dataclass
class Resolved:
    key: str
    text: str | None  # None: missing
    personal: bool = False
    ficha_value_id: uuid.UUID | None = None
    circuit_id: uuid.UUID | None = None
    bom_item_id: uuid.UUID | None = None
    field: str | None = None

    @property
    def missing(self) -> bool:
        return self.text is None


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, int | float | Decimal):
        return number_text(value)
    if isinstance(value, list):
        return ", ".join(format_value(v) for v in value)
    return str(value).strip()


@dataclass
class ValueSource:
    """Everything one revision can say, looked up by placeholder key."""

    revision_id: uuid.UUID
    values: dict[str, FichaValue]
    circuits: dict[str, Circuit]
    bom: dict[str, BomItem]
    profile: dict[str, str] = field(default_factory=dict)  # tec.* and doc.local (task 6)

    @classmethod
    def load(cls, db: Session, revision: FichaRevision, profile: dict[str, str] | None = None
             ) -> "ValueSource":  # fmt: skip
        values = {
            v.key: v
            for v in db.scalars(select(FichaValue).where(FichaValue.revision_id == revision.id))
        }
        circuits: dict[str, Circuit] = {}
        for c in db.scalars(select(Circuit).where(Circuit.revision_id == revision.id)):
            circuits.setdefault(circuit_slug(c), c)
        bom: dict[str, BomItem] = {}
        for b in db.scalars(select(BomItem).where(BomItem.revision_id == revision.id)):
            if b.code:
                bom.setdefault(bom_slug(b), b)
        return cls(revision.id, values, circuits, bom, dict(profile or {}))

    def resolve(self, key: str) -> Resolved:
        if key in EMPTY_BY_DESIGN:
            return Resolved(key, "")
        if key.startswith(("tec.", "doc.")):
            text = self.profile.get(key)
            return Resolved(key, text or None, personal=key in PERSONAL_DOC_KEYS)
        if key.startswith("circ."):
            return self._circuit(key)
        if key.startswith("bom."):
            return self._bom(key)
        fv = self.values.get(key)
        if fv is None or fv.value in (None, "", []):
            return Resolved(key, None, personal=bool(KEYS.get(key) and KEYS[key].personal))
        return Resolved(key, format_value(fv.value), fv.personal_data, ficha_value_id=fv.id)

    def _circuit(self, key: str) -> Resolved:
        m = re.fullmatch(r"circ\.([a-z0-9_]+)\.([a-z0-9_]+)", key)
        c = self.circuits.get(m.group(1)) if m else None
        if m is None or c is None or m.group(2) not in CIRCUIT_FIELDS:
            return Resolved(key, None)
        value = getattr(c, m.group(2))
        text = None if value in (None, "") else format_value(value)
        return Resolved(key, text, circuit_id=c.id, field=m.group(2))

    def _bom(self, key: str) -> Resolved:
        m = re.fullmatch(r"bom\.([a-z0-9_]+)\.([a-z0-9_]+)", key)
        b = self.bom.get(m.group(1)) if m else None
        if m is None or b is None or m.group(2) not in BOM_FIELDS:
            return Resolved(key, None)
        value = getattr(b, m.group(2))
        text = None if value in (None, "") else format_value(value)
        return Resolved(key, text, bom_item_id=b.id, field=m.group(2))

    def available(self) -> list[dict[str, str]]:
        """Keys with a value, with their label (what the LLM may use, Phase 4 task 4)."""
        out = [{"key": k, "label": key_label(k), "unit": KEYS[k].unit or ""}
               for k, v in sorted(self.values.items())
               if k in KEYS and v.value not in (None, "", [])]  # fmt: skip
        for s, c in sorted(self.circuits.items()):
            for f in ("kva", "in_a", "section_mm2", "cable_raw", "installation", "length_m"):
                if getattr(c, f) not in (None, ""):
                    where = f"{c.origin} → {c.destination}"
                    out.append({"key": f"circ.{s}.{f}", "label": f"{where}: {f}", "unit": ""})
        return out


def label(key: str) -> str:
    if key.startswith("circ."):
        return "Troço " + key.split(".")[1] + " · " + key.rsplit(".", 1)[-1]
    if key.startswith("bom."):
        return "Artigo " + key.split(".")[1].replace("_", ".") + " · " + key.rsplit(".", 1)[-1]
    return key_label(key)
