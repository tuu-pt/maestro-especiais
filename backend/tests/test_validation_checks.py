"""TIP-01, DES-01 and CAL-01 on small contexts (task 4c). R1/R2 in test_validation_rules.py."""

from types import SimpleNamespace
from typing import Any, cast

from app.validation.context import Context
from app.validation.pieces import Paragraph, Piece, PieceData
from app.validation.rules import cal_01


def mdj(*texts: tuple[str, str]) -> Context:
    piece = Piece(ref="doc:1", kind="MDJ", origin="existing", content_hash="x")
    paragraphs = [Paragraph("doc:1", key, key, "block", n, text)
                  for n, (key, text) in enumerate(texts)]  # fmt: skip
    return Context(cast(Any, None), cast(Any, SimpleNamespace(id=None)), cast(Any, None),
                   {"doc:1": piece}, {"doc:1": PieceData(paragraphs=paragraphs)})  # fmt: skip


def test_cal_01_reads_the_limits_the_mdj_states() -> None:
    ctx = mdj(
        ("dimensionamento_eletrico.quedas_de_tensao", "não deverá ser superior a 3% (para "
         "circuitos de iluminação) ou a 5% (para circuitos de outros usos) da tensão nominal"),
        ("dimensionamento_eletrico.poder_de_corte_dos_aparelhos_de_protecao",
         "Toda a aparelhagem de corte e proteção deve ter o poder de corte nunca inferior a 6KA."),
    )  # fmt: skip

    found = cal_01.limits(ctx)

    assert {k: v[0] for k, v in found.items()} == {"lighting": 3.0, "other": 5.0, "breaking": 6.0}
    assert found["breaking"][1].endswith("parágrafo 2")


def test_cal_01_without_limits_in_the_mdj_is_not_comparable() -> None:
    ctx = mdj(("dimensionamento_eletrico.quedas_de_tensao", "Dentro dos limites das RTIEBT."))
    ctx.circuits = [cast(Any, SimpleNamespace(
        id=1, origin="A", destination="B", row_index=1, source_ref="Tabela!linha 5",
        ib_a=None, in_a=None, iz_a=None, i2_a=None, iz145_a=None, vd_total_pct=2,
        breaking_capacity_ka=6))]  # fmt: skip

    found = list(cal_01.RULE.check(ctx))

    assert [f.severity for f in found] == ["info"]
    assert "não comparável" in found[0].message


def test_tip_01_names_of_other_projects_but_not_this_projects_own() -> None:
    from app.validation.pieces import Fact
    from app.validation.rules import tip_01

    ctx = mdj(("introducao", "Obra da Biblioteca Municipal de Aldeia Velha, requerente Rui."),
              ("introducao", "Moradia do requerente Ana Maria Costa."))  # fmt: skip
    ctx.data["doc:1"].facts.append(
        Fact("id.requerente.nome", "Ana Maria Costa", "doc:1", personal=True)
    )  # another project's, in a piece: flagged
    ctx.memo = {}
    ctx.__dict__["other_projects_names"] = [
        ("R2", "id.obra.designacao", "Biblioteca Municipal de Aldeia Velha"),  # same work
        ("R1", "id.requerente.nome", "Ana Maria Costa"),
    ]
    ctx.ficha = {
        "id.obra.designacao": cast(
            Any, SimpleNamespace(value="Biblioteca Municipal de Aldeia Velha")
        )
    }  # this project's own work

    found = tip_01.other_projects(ctx)

    assert [f.evidence["project"] for f in found] == ["R1", "R1"]  # the text and the piece
    assert {f.evidence["value"] for f in found} == {"•••"}
