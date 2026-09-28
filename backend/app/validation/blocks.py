"""The blocks each written piece should have, by the activation rules (SPEC 8.3; COE-03, CNT-01).

The rules of the skeleton (Phase 3) are evaluated on the confirmed ficha-base, as the assembly
does. A block whose rule is always true is part of the skeleton (CNT-01 when missing); a block
whose rule depends on a system of the project is COE-03 (missing, or present with no system).
Blocks are matched by their key (the slug of the titles): a piece whose titles differ from the
library is reported as missing blocks [A CONFIRMAR].
"""

from dataclasses import dataclass

from sqlalchemy import select

from app.library.preview import revision_context
from app.library.rules import evaluate, explain
from app.models import TemplateBlock
from app.validation.context import Context
from app.validation.extract.documents import PREFIX
from app.validation.pieces import Piece

ALWAYS = ("", "true")


@dataclass(frozen=True)
class Expected:
    key: str  # without the document prefix, as SectionInfo.key
    title: str
    level: int
    rule: str
    active: bool
    why: str | None  # why the rule is false


def _expected(ctx: Context) -> dict[str, list[Expected]]:
    if "blocks" in ctx.memo:
        return ctx.memo["blocks"]  # type: ignore[no-any-return]
    rule_ctx, _ = revision_context(ctx.db, ctx.revision.id)
    out: dict[str, list[Expected]] = {"MDJ": [], "CTE": []}
    blocks = ctx.db.scalars(
        select(TemplateBlock).where(TemplateBlock.kind == "block", TemplateBlock.version == 1,
                                    TemplateBlock.status != "rejected")
        .order_by(TemplateBlock.order)
    ).all()  # fmt: skip
    for b in blocks:
        prefix = PREFIX.get(b.doc_type, "")
        tree = b.activation_ast
        active = evaluate(tree, rule_ctx) if tree else True
        why = explain(tree, rule_ctx) if tree and not active else None
        rule = (b.activation_rule or "").strip()
        out[b.doc_type].append(Expected(b.key[len(prefix) :], b.title, b.level, rule, active, why))
    ctx.memo["blocks"] = out
    return out


def expected(ctx: Context, piece: Piece) -> list[Expected]:
    return _expected(ctx).get(piece.kind, [])


def present(ctx: Context, piece: Piece) -> dict[str, bool]:
    """Section key -> active, as the piece has them."""
    return {s.key: s.active for s in ctx.sections(piece) if s.kind == "block"}
