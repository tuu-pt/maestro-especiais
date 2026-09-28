"""CNT-01 (SPEC 9): a mandatory block of the skeleton is missing.

A block whose activation rule is always true (SPEC 8.3) is mandatory. Also a mandatory value of
an active block: the MDJ must state the power to supply when the ficha-base has it (C6: the MDJ
of R2 says nothing) [A CONFIRMAR: which values are mandatory].
"""

from app.validation.blocks import ALWAYS, expected, present
from app.validation.compare import WRITTEN, location, shown
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, Finding, Rule
from app.validation.extract.text import POWER

MANDATORY_VALUES = {"MDJ": {POWER: "a potência a alimentar"}}


def check(ctx: Context) -> list[Finding]:
    out = []
    for piece in ctx.of_kind(*WRITTEN):
        has = present(ctx, piece)
        for block in expected(ctx, piece):
            if block.rule in ALWAYS and not has.get(block.key):
                out.append(RULE.finding(
                    f"{piece.name}: falta o bloco obrigatório «{block.title}».",
                    key=f"block|{piece.ref}|{block.key}", location=location(piece),
                    evidence={"block": block.title, "section": block.key},
                    likely_reading=f"Bloco em falta {piece.in_label}.",
                    suggested_fix="Acrescentar o bloco do esqueleto (SPEC 8.3).",
                    actions=[OPEN_EDITOR],
                ))  # fmt: skip
        facts = {f.key for f in ctx.data[piece.ref].facts}
        for key, what in MANDATORY_VALUES.get(piece.kind, {}).items():
            reference = ctx.ficha_value(key)
            if reference is None or key in facts:
                continue
            out.append(RULE.finding(
                f"{piece.name}: não indica {what} (a ficha-base tem {shown(reference)}).",
                key=f"value|{piece.ref}|{key}", location=location(piece),
                evidence={"value": what, "reference": shown(reference)},
                likely_reading=f"Valor em falta {piece.in_label}.",
                suggested_fix="Escrever o valor da ficha-base na secção de alimentação de energia.",
                actions=[OPEN_EDITOR],
            ))  # fmt: skip
    return out


RULE = Rule("CNT-01", "content", "warning", "Bloco ou valor obrigatório em falta", check)
