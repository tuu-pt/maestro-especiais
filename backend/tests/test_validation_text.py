"""TXT-01, CCP-01 on small contexts (task 4d). R1/R2 in test_validation_rules.py."""

from types import SimpleNamespace
from typing import Any, cast

from app.validation.context import Context
from app.validation.pieces import Paragraph, Piece, PieceData
from app.validation.rules import ccp_01, txt_01


def cte(*texts: tuple[str, str], public: bool = False) -> Context:
    piece = Piece(ref="doc:1", kind="CTE", origin="existing", content_hash="x")
    paragraphs = [Paragraph("doc:1", key, key.title(), "block", n, text)
                  for n, (key, text) in enumerate(texts)]  # fmt: skip
    project = SimpleNamespace(id=None, public_procurement=public)
    return Context(cast(Any, None), cast(Any, project), cast(Any, None), {"doc:1": piece},
                   {"doc:1": PieceData(paragraphs=paragraphs)})  # fmt: skip


def test_txt_01_a_sentence_broken_by_a_line_break_c13() -> None:
    ctx = cte(("quedas", "O cálculo será em função da secção dos condutores, dos"),
              ("quedas", "tipos de circuito (monofásico e trifásico)."))  # fmt: skip

    found = list(txt_01.RULE.check(ctx))

    assert [f.evidence["kind"] for f in found] == ["break"]
    assert "⏎" in found[0].evidence["excerpt"]


def test_txt_01_repeated_reference_and_near_duplicate_items() -> None:
    ctx = cte(
        ("interruptores", "Comutador de escada: Ref. 45070 S ou Ref. 45071 S, ou 45070 S"),
        ("legislacao_e_normas", "Normas portuguesas aplicáveis e, na sua ausência, CEI."),
        ("legislacao_e_normas", "Normas portuguesas aplicáveis, as recomendações da IEC."),
    )

    kinds = sorted(f.evidence["kind"] for f in txt_01.RULE.check(ctx))

    assert kinds == ["near", "reference"]


def test_ccp_01_only_in_public_procurement() -> None:
    text = ("videoporteiro", "Placa exterior da marca Comelit, modelo Mini, com ecrã tátil.")
    ok = ("tomadas", "Tomada Schuko da marca EFAPEL, série SIZA, ou equivalente.")

    assert list(ccp_01.RULE.check(cte(text, ok))) == []
    found = list(ccp_01.RULE.check(cte(text, ok, public=True)))
    assert [f.location["section"] for f in found] == ["videoporteiro"]
