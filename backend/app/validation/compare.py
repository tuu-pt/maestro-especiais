"""What the coherence rules share: observations per piece, the reference, masked evidence."""

from collections.abc import Callable, Iterable
from typing import Any

from app.ingest import boards as board_names
from app.validation.context import Context
from app.validation.likely import Divergence, Observation, split
from app.validation.normalize import same, shown_number
from app.validation.pieces import MASK, Fact, Paragraph, Piece

# Pieces that are written by people (and assembled by the tool): the ones the COE-01 severity
# and the "only one piece" reading are about.
WRITTEN = ("MDJ", "CTE")
BOM = ("MQT", "LPU")


def observations(ctx: Context, key: str, kinds: Iterable[str] | None = None) -> list[Observation]:
    """One comparable fact per piece (the first), for the pieces of the given kinds."""
    wanted = set(kinds) if kinds is not None else None
    seen: set[str] = set()
    out = []
    for f in ctx.facts(key):
        piece = ctx.pieces.get(f.piece)
        if piece is None or f.piece in seen or (wanted is not None and piece.kind not in wanted):
            continue
        seen.add(f.piece)
        out.append(Observation(piece, f))
    return out


def shown(value: Any, personal: bool = False) -> str:
    if personal:
        return MASK
    if value is None or value == "":
        return "(sem valor)"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, int | float):
        return shown_number(float(value))
    if isinstance(value, list):
        return ", ".join(shown(v) for v in value)
    return str(value)


def evidence(
    ctx: Context, reference: Any, reference_label: str, obs: list[Observation],
    divergent: Iterable[Observation], personal: bool = False,
) -> dict[str, Any]:  # fmt: skip
    """Values per piece (masked when personal), the reference and where each was read."""
    bad = {o.piece.ref for o in divergent}
    return {
        "reference": {"label": reference_label, "value": shown(reference, personal)},
        "values": [
            {"piece": o.piece.ref, "piece_name": o.piece.name, "column": o.piece.column,
             "value": MASK if personal or o.fact.personal else o.fact.display(),
             "differs": o.piece.ref in bad, "where": where_label(o.fact),
             "note": ctx.mask(o.fact.note) if o.fact.note else None}
            for o in obs
        ],
        "masked": personal,
    }  # fmt: skip


def where_label(fact: Fact) -> str:
    loc = fact.locator or {}
    if loc.get("section_title"):
        para = loc.get("paragraph")
        return f"{loc['section_title']}" + (f", parágrafo {para + 1}" if para is not None else "")
    return str(loc.get("cell") or loc.get("page") or "")


def location(piece: Piece | None, fact: Fact | None = None) -> dict[str, Any]:
    loc = dict(fact.locator) if fact else {}
    if piece is not None:
        loc.update({"piece": piece.ref, "piece_name": piece.name, "column": piece.column,
                    "document_id": piece.document_id, "file_id": piece.file_id})  # fmt: skip
    return loc


def compare(reference: Any, obs: list[Observation],
            equal: Callable[[Any, Any], bool] = same) -> Divergence:  # fmt: skip
    return split(reference, obs, equal)


def board_count(names: list[Any] | None) -> int | None:
    if not names:
        return None
    return len({board_names.core(str(n)) for n in names if board_names.core(str(n))})


def paragraph_location(ctx: Context, p: Paragraph) -> dict[str, Any]:
    piece = ctx.pieces.get(p.piece)
    loc: dict[str, Any] = {
        "section": p.section_key,
        "section_title": p.section_title,
        "section_id": p.section_id,
        "paragraph": p.index,
        "anchor": p.anchor,
    }
    return {**location(piece), **loc}


def excerpt(ctx: Context, text: str, start: int = 0, end: int | None = None,
            around: int = 60) -> str:  # fmt: skip
    """A masked excerpt around [start, end) of a paragraph."""
    end = start if end is None else end
    left, right = max(0, start - around), min(len(text), end + around)
    out = ("…" if left else "") + text[left:right].strip() + ("…" if right < len(text) else "")
    return ctx.mask(" ".join(out.split()))
