"""A block seen with the ficha-base of a project (curator screen, Phase 3).

Placeholders are resolved from the latest revision of the ficha, personal values stay masked
(there is no reveal here), and the activation rule is evaluated on the same project. Nothing is
written: the assembly of the documents is Phase 4.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.consolidate import latest_revision
from app.ingest.keys import KEYS
from app.library.facts import DOC_KEYS, UNITS, number_text
from app.library.rules import CIRCUIT_FIELDS, Context, RuleError, evaluate, parse
from app.models import BomItem, Circuit, FichaValue, TemplateBlock

PLACEHOLDER = re.compile(r"\{\{v:([a-z0-9_.]+)\}\}")
MASK = "•••"


def label(key: str) -> str:
    if key in KEYS:
        return KEYS[key].label_pt
    return DOC_KEYS.get(key, key)


def project_context(db: Session, project_id: uuid.UUID) -> tuple[Context, dict[str, FichaValue]]:
    """Context of the latest revision of the ficha-base (preview: any revision)."""
    revision = latest_revision(db, project_id)
    if revision is None:
        return Context(), {}
    return revision_context(db, revision.id)


def revision_context(db: Session, revision_id: uuid.UUID) -> tuple[Context, dict[str, FichaValue]]:
    """What the rules see of one revision: values, circuits, articles and their links."""
    values = {
        v.key: v
        for v in db.scalars(select(FichaValue).where(FichaValue.revision_id == revision_id))
    }
    ctx = Context(values={k: v.value for k, v in values.items()})
    for c in db.scalars(select(Circuit).where(Circuit.revision_id == revision_id)):
        ctx.circuits.append({f: getattr(c, f, None) for f in CIRCUIT_FIELDS})
    chapter = None
    items = db.scalars(
        select(BomItem).where(BomItem.revision_id == revision_id).order_by(BomItem.row_index)
    )
    for item in items:
        if item.kind == "chapter":
            chapter = item.designation
        ctx.bom.append({"designation": item.designation, "chapter": chapter, "unit": item.unit})
        if item.link_key:
            ctx.linked.add(item.link_key)
    return ctx, values


def _shown(key: str, value: FichaValue | None) -> tuple[str | None, bool]:
    """(text to show or None when missing, masked)."""
    if value is None or value.value in (None, "", []):
        return None, False
    if value.personal_data:
        return MASK, True
    raw = value.value
    if key in UNITS or isinstance(raw, int | float):
        try:
            return number_text(raw), False
        except (ValueError, ArithmeticError):
            return str(raw), False
    if isinstance(raw, list):
        return ", ".join(str(x) for x in raw), False
    return str(raw), False


@dataclass
class Paragraph:
    mode: str
    text: str | None  # resolved; None for adaptive paragraphs (written in Phase 4)
    missing: list[str] = field(default_factory=list)  # keys with no value
    masked: list[str] = field(default_factory=list)  # personal keys, shown as •••


@dataclass
class Preview:
    active: bool | None
    rule_error: str | None
    paragraphs: list[Paragraph]


def resolve(text: str, values: dict[str, FichaValue]) -> Paragraph:
    missing: list[str] = []
    masked: list[str] = []

    def one(m: re.Match[str]) -> str:
        key = m.group(1)
        shown, is_masked = _shown(key, values.get(key))
        if shown is None:
            missing.append(key)
            return f"[falta: {label(key)}]"
        if is_masked:
            masked.append(key)
        return shown

    return Paragraph("parametric", PLACEHOLDER.sub(one, text), missing, masked)


def preview(db: Session, block: TemplateBlock, project_id: uuid.UUID) -> Preview:
    ctx, values = project_context(db, project_id)
    active: bool | None
    try:
        active = evaluate(parse(block.activation_rule or "true"), ctx)
        error = None
    except RuleError as exc:
        active, error = None, str(exc)
    paragraphs: list[Paragraph] = []
    for entry in block.body_template:
        text: str | None = entry.get("text")
        if entry["mode"] == "adaptive" or text is None:
            paragraphs.append(Paragraph(entry["mode"], None))
        else:
            resolved = resolve(text, values)
            resolved.mode = entry["mode"]
            paragraphs.append(resolved)
    return Preview(active, error, paragraphs)


def keys_in(entries: list[dict[str, Any]]) -> list[str]:
    return sorted({k for e in entries for k in PLACEHOLDER.findall(e.get("text") or "")})
