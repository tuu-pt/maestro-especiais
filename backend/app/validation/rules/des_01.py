"""DES-01 (SPEC 9): the index of the drawings (EL001…) does not match the sheets of the PDF (C4).

The comparison is the one the ficha already shows (Phase 2, drawings.index_check): by the digits
of the codes, the index sheet itself need not be listed.
"""

from typing import Any

from app.ingest.drawings import index_check
from app.validation.compare import location
from app.validation.context import Context
from app.validation.core import OPEN_FICHA, Finding, Rule


def _value(ctx: Context, piece_ref: str, key: str) -> Any:
    return next((f.value for f in ctx.data[piece_ref].facts if f.key == key), None)


def check(ctx: Context) -> list[Finding]:
    out = []
    for piece in ctx.of_kind("DRAWINGS"):
        index = _value(ctx, piece.ref, "pd.indice") or []
        sheets = _value(ctx, piece.ref, "pd.folhas") or []
        pages = _value(ctx, piece.ref, "pd.n_paginas_pdf")
        if not index or pages is None:
            continue
        found = index_check(index, sheets, int(pages))
        if found["matches"] and len(index) <= int(pages):
            continue
        parts = [f"o índice lista {len(index)} folhas e o PDF tem {pages} páginas"]
        if found["missing_in_pdf"]:
            parts.append("folhas do índice sem página: " + ", ".join(found["missing_in_pdf"]))
        if found["not_in_index"]:
            parts.append("páginas fora do índice: " + ", ".join(map(str, found["not_in_index"])))
        out.append(RULE.finding(
            "Peças desenhadas: " + "; ".join(parts) + ".",
            key=f"{piece.ref}|{len(index)}|{pages}|{','.join(found['missing_in_pdf'])}",
            location=location(piece),
            evidence=found,
            likely_reading="Folha em falta no PDF ou índice desatualizado.",
            suggested_fix="Acrescentar a folha ao PDF ou atualizar o índice.",
            actions=[OPEN_FICHA],
        ))  # fmt: skip
    return out


RULE = Rule("DES-01", "drawings", "warning", "Índice ≠ folhas do PDF", check)
