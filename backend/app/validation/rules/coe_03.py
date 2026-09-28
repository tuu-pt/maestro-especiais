"""COE-03 (SPEC 9): a system of the project with no block in the MDJ or the CTE, or the inverse.

E.g. buried circuits (ENT) in the Tabela de Cálculo and no block of buried cables in the MDJ
(C12). The systems are the conditions of the activation rules of the skeleton (SPEC 8.3).
"""

from app.validation.blocks import ALWAYS, expected, present
from app.validation.compare import WRITTEN, location
from app.validation.context import Context
from app.validation.core import OPEN_EDITOR, OPEN_FICHA, Finding, Rule


def check(ctx: Context) -> list[Finding]:
    out = []
    for piece in ctx.of_kind(*WRITTEN):
        has = present(ctx, piece)
        for block in expected(ctx, piece):
            if block.rule in ALWAYS:
                continue  # part of the skeleton: CNT-01
            active_in_piece = has.get(block.key)
            if block.active and not active_in_piece:
                out.append(RULE.finding(
                    f"{piece.name}: falta o bloco «{block.title}», e o projeto tem o sistema "
                    "correspondente.",
                    key=f"missing|{piece.ref}|{block.key}", location=location(piece),
                    evidence={"block": block.title, "rule": block.rule,
                              "section": block.key},
                    likely_reading=f"Bloco em falta {piece.in_label}.",
                    suggested_fix="Acrescentar o bloco (na montagem: ativar a secção).",
                    actions=[OPEN_EDITOR],
                ))  # fmt: skip
            elif not block.active and active_in_piece:
                out.append(RULE.finding(
                    f"{piece.name}: tem o bloco «{block.title}», mas o projeto não tem o sistema "
                    "correspondente.",
                    key=f"extra|{piece.ref}|{block.key}", location=location(piece),
                    evidence={"block": block.title, "rule": block.rule, "why": block.why,
                              "section": block.key},
                    likely_reading="Texto herdado de outro projeto, ou falta o sistema na "
                    "ficha-base.",
                    actions=[OPEN_EDITOR, OPEN_FICHA],
                ))  # fmt: skip
    return out


RULE = Rule("COE-03", "coherence", "warning", "Sistema sem bloco, ou bloco sem sistema", check)
