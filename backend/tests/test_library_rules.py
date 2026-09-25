"""Activation rules: the language, its errors and the rules proposed for SPEC 8.3 (task 4)."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.library.context import fixture_context
from app.library.rules import Context, RuleError, check, parse
from app.library.seed import seed_blocks
from app.library.skeleton import EXPECTED_DIFFERENCES, MDJ_RULES
from app.library.sources import seed_sources
from app.models import TemplateBlock
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
HAVE_FIXTURES = (FIXTURES / "R1").is_dir() and (FIXTURES / "R2").is_dir()


# ---------------------------------------------------------------- the language


def test_trees() -> None:
    assert parse("sys.fv.present") == {"op": "present", "key": "sys.fv"}
    assert parse('ele.classificacao != "Locais de habitação"') == {
        "op": "cmp", "key": "ele.classificacao", "cmp": "!=", "value": "Locais de habitação",
    }  # fmt: skip
    assert parse('any circuit.installation == "ENT"') == {
        "op": "any", "collection": "circuit", "field": "installation", "cmp": "==", "value": "ENT",
    }  # fmt: skip
    assert parse('ele.entrada in ["Trif", "Mono"]')["value"] == ["Trif", "Mono"]
    assert parse("ele.potencia_alimentar_kva > 41,4")["value"] == 41.4
    assert parse("true") == {"op": "const", "value": True}


def test_and_binds_tighter_than_or_and_not_applies_to_what_follows() -> None:
    tree = parse("sys.fv.present or sys.ve.present and not sys.ups.present")

    assert tree["op"] == "or"
    assert tree["args"][1] == {
        "op": "and",
        "args": [{"op": "present", "key": "sys.ve"},
                 {"op": "not", "arg": {"op": "present", "key": "sys.ups"}}],
    }  # fmt: skip
    assert parse("(sys.fv.present or sys.ve.present) and sys.ups.present")["op"] == "and"


@pytest.mark.parametrize(
    ("rule", "message", "position"),
    [
        ("", "A regra está vazia", 1),
        ("sys.fv", "Falta a comparação depois de «sys.fv» (ou «.present»)", 7),
        ("ele.x == 1", "Chave desconhecida «ele.x»", 1),
        ("any foo.x == 1", "«any» só se aplica a circuit ou bom, não a «foo»", 5),
        ("any bom.price > 3", "Campo desconhecido «price» em bom", 5),
        ('ele.entrada in "Trif"', 'Depois de «in» vem uma lista: ["a", "b"]', 13),
        ("(sys.fv.present", "Esperava «)», encontrei o fim da regra", 16),
        ("sys.fv.present sys.ve.present", "Esperava o fim, encontrei «sys.ve.present»", 16),
        ('__import__("os")', "Chave desconhecida «__import__»", 1),
        ("sys.fv.present; 1", "Carácter inesperado «;»", 15),
    ],
)
def test_errors_say_what_and_where(rule: str, message: str, position: int) -> None:
    with pytest.raises(RuleError) as error:
        parse(rule)

    assert error.value.message == message
    assert error.value.position + 1 == position
    assert str(error.value).endswith(f"(posição {position})")


def test_evaluation() -> None:
    ctx = Context(
        values={"ele.classificacao": "Estabelecimentos recebendo público",
                "ele.potencia_alimentar_kva": 180, "ele.entrada": "Trif"},
        linked={"sys.fv"},
        circuits=[{"installation": "EST"}, {"installation": "ENT"}],
        bom=[{"designation": "Módulo fotovoltaico", "chapter": "FOTOVOLTAICO", "unit": "un"}],
    )  # fmt: skip

    assert check('ele.classificacao != "Locais de habitação"', ctx)
    assert check('ele.classificacao ~ "RECEBENDO publico"', ctx)  # no case, no accents
    assert check("ele.potencia_alimentar_kva > 41,4", ctx)
    assert check('ele.entrada in ["Mono", "trif"]', ctx)
    assert check("sys.fv.present and not sys.ve.present", ctx)
    assert check('any circuit.installation == "ENT"', ctx)
    assert check('any bom.chapter ~ "fotovoltaico"', ctx)
    assert not check('any bom.designation ~ "vala"', ctx)
    # with no value, a test is false (either way)
    assert not check('ele.contagem == "Direta"', ctx)
    assert not check('ele.contagem != "Direta"', ctx)
    assert not check("ele.n_ramais > 0", ctx)
    assert not check('ele.classificacao > "A"', ctx)  # no order between texts


# ---------------------------------------------------------------- the rules on R1 and R2


@pytest.fixture
def seeded(db: Session, store: ObjectStore) -> list[TemplateBlock]:
    if not HAVE_FIXTURES:
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))
    order = (TemplateBlock.doc_type.desc(), TemplateBlock.order)  # MDJ, then CTE
    return list(db.scalars(select(TemplateBlock).order_by(*order)))


def test_every_block_has_a_rule_that_parses(seeded: list[TemplateBlock]) -> None:
    for b in seeded:
        assert b.activation_rule, b.key
        assert b.activation_ast == parse(b.activation_rule)
    assert {b.key for b in seeded} >= set(MDJ_RULES)


def test_the_rules_reproduce_the_mdj_of_r1_and_r2(seeded: list[TemplateBlock]) -> None:
    ctx = {code: fixture_context(FIXTURES, code) for code in ("R1", "R2")}

    differences = {}
    for b in seeded:
        for code in ("R1", "R2"):
            active = check(b.activation_rule or "", ctx[code])
            in_mdj = code in b.projects
            if active != in_mdj:
                differences[(b.key, code)] = "ativa sem bloco" if active else "bloco sem regra"
    assert set(differences) == set(EXPECTED_DIFFERENCES)
    # C12: a buried circuit in R2 and no "canalizações enterradas" in its MDJ
    assert differences[("ele.mdj.canalizacoes.canalizacoes_enterradas", "R2")] == "ativa sem bloco"


def test_the_skeleton_block_no_reference_has(seeded: list[TemplateBlock]) -> None:
    b = next(b for b in seeded if b.key.endswith(".iluminacao_de_seguranca"))
    after = seeded[seeded.index(b) - 1]

    assert after.key == "ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_normal"
    assert b.projects == [] and b.body_template == [] and b.status == "proposed"
    assert b.notes == ["Esqueleto 8.3: nenhum projeto de referência tem este bloco; falta o texto."]


def test_fixture_contexts() -> None:
    if not HAVE_FIXTURES:
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    r1, r2 = fixture_context(FIXTURES, "R1"), fixture_context(FIXTURES, "R2")

    assert r1.values["ele.classificacao"] == "Locais de habitação"
    assert {"sys.fv", "sys.ve"} <= r2.linked and not {"sys.fv", "sys.ve"} & r1.linked
    assert any(c["installation"] == "ENT" for c in r2.circuits)
    assert any(b["chapter"] == "AUDIOVISUAL" for b in r2.bom)
