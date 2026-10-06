"""Equipment library proposed from the reference CTEs, with the requirements (Phase 7, task 1)."""

import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_library_blocks import PLACEHOLDER, _known_values

from app.equipment import block_category
from app.equipment.cte import read_section, reference_line
from app.equipment.params import read, satisfies
from app.equipment.seed import seed_equipment
from app.library import privacy
from app.library.docx_blocks import split
from app.library.seed import seed_blocks
from app.library.sources import reference_documents, seed_sources
from app.models import Equipment, Requirement
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
HAVE_FIXTURES = (FIXTURES / "R1").is_dir() and (FIXTURES / "R2").is_dir()
needs_fixtures = pytest.mark.skipif(not HAVE_FIXTURES, reason="data/fixtures/R1 e R2")


# ---------------------------------------------------------------- parameters


def values(text: str) -> list[tuple[str, Any]]:
    return [(r.name, r.value) for r in read(text)]


def test_parameters_are_read_as_written() -> None:
    assert values("Caixa Base: Plástico \u2013 PSHI / IP55 / IK10 / ICC(KA): 25KA") == [
        ("ip_rating", "IP55"), ("ik_rating", "IK10"), ("icc_ka", 25.0)]  # fmt: skip
    assert values("redondo Ø96mm, 1,5W, IP65 IK10") == [
        ("power_w", 1.5), ("ip_rating", "IP65"), ("ik_rating", "IK10")]  # fmt: skip
    assert values("potência nominal de 590 Wp e eficiência máxima de 22,8%") == [
        ("peak_power_wp", 590.0), ("efficiency_pct", 22.8)]  # fmt: skip
    assert values("100lm, autonomia de 1 hora") == [
        ("luminous_flux_lm", 100.0), ("autonomy_h", 1.0)]  # fmt: skip
    assert values("Campo de deteção com 14 m \u2013 360º") == [
        ("detection_range_m", 14.0), ("detection_angle_deg", 360.0)]  # fmt: skip
    assert values("carregadores de 7,4kW, 4000K") == [
        ("power_kw", 7.4), ("color_temperature_k", 4000.0)]  # fmt: skip
    assert values("Autoextinguibilidade: 960 ºC; MOODLINER 1812WP") == []  # not an angle, a name


@pytest.mark.parametrize(
    ("name", "operator", "required", "offered", "ok"),
    [("ip_rating", ">=class", "IP55", "IP65", True),
     ("ip_rating", ">=class", "IP55", "IP44", False),
     ("ip_rating", ">=class", "IP54", "IPX4", None),  # dust not said: not comparable
     ("ip_rating", ">=class", "IPX4", "IP44", True),
     ("ik_rating", ">=class", "IK08", "IK10", True),
     ("cpr_class", ">=class", "Cca", "B2ca", True),
     ("cpr_class", ">=class", "Cca", "Eca", False),
     ("icc_ka", ">=", 25, 20, False),
     ("power_w", "=", 30, 30.0, True),
     ("dimensions_mm", "info", "160x160", "150x150", None)],
)  # fmt: skip
def test_a_requirement_compares_minimums_and_classes(
    name: str, operator: str, required: Any, offered: Any, ok: bool | None
) -> None:
    assert satisfies(name, operator, required, offered) is ok


# ---------------------------------------------------------------- reference lines of the CTE


def test_a_reference_line_names_the_maker_and_the_model_or_the_reference() -> None:
    portinhola = reference_line(
        "Portinhola PBT Tri, referência +32470 da marca Quitérios, ou equivalente.", 3
    )
    assert portinhola is not None
    assert (portinhola.name, portinhola.manufacturer, portinhola.reference) == (
        "Portinhola PBT Tri", "Quitérios", "+32470")  # fmt: skip
    switch = reference_line(
        "Interruptor unipolar \u2013 EFAPEL \u2013 SIZA Ref. 45011 S ou equivalente:", 1
    )
    assert switch is not None and (switch.model, switch.reference) == ("SIZA", "45011 S")
    door = reference_line("Modelo: Hikvision DS-KH6320-LE1(B)", 4, "Videoporteiro")
    assert door is not None and door.or_equivalent is False and door.name == "Videoporteiro"
    assert reference_line("Os quadros elétricos deverão ter classe II, da marca Quitérios, "
                          "ou equivalente.", 0) is None  # a maker without a model  # fmt: skip


def test_only_the_special_conditions_are_about_equipment() -> None:
    assert block_category("ele.cte.condicoes_tecnicas_especiais.entrada_de_energia") == "portinhola"
    assert block_category("ele.cte.condicoes_tecnicas_especiais.videoporteiro") == "videoporteiro"
    assert block_category("ele.cte.condicoes_tecnicas_gerais.introducao") is None


def _cte(code: str) -> dict[str, Any]:
    [data] = [d for t, _, d in reference_documents(FIXTURES, code) if t == "CTE"]
    out = {}
    for s in split(data).sections:
        lines = [(i, privacy.mask(t)) for i, t in enumerate(s.text.splitlines())]
        reading = read_section(f"ele.cte.{s.key}", lines, s.title)
        if reading is not None:
            out[s.key.rsplit(".", 1)[-1]] = reading
    return out


@needs_fixtures
def test_the_equipment_of_the_cte_of_r1() -> None:
    r1 = _cte("R1")

    supply = r1["entrada_de_energia"]
    assert [(f.name, f.reference) for f in supply.found] == [
        ("Portinhola PBT Tri", "+32470"), ("Caixa para contador trifásico", "+302")]  # fmt: skip
    block = {(n.param, n.value) for n in supply.needs if n.owner is None}
    assert block == {("ip_rating", "IP55"), ("ik_rating", "IK10"), ("icc_ka", 25.0)}
    detectors = r1["detetores_de_movimento"].found
    assert [f.model for f in detectors] == ["1SP SP020", "1SP SP010"]
    first = {(r.name, r.value) for r in detectors[0].readings}
    assert {("detection_range_m", 14.0), ("detection_angle_deg", 360.0)} <= first
    assert [f.code for f in r1["iluminacao_normal"].found] == ["L1", "L7", "L8", "L9", "L14", "L15"]
    door = r1["videoporteiro"].found
    assert {f.manufacturer for f in door} == {"Hikvision"}
    assert not any(f.or_equivalent for f in door)


@needs_fixtures
def test_the_equipment_of_the_cte_of_r2() -> None:
    r2 = _cte("R2")

    [module] = r2["modulos_fotovoltaicos"].found
    assert (module.manufacturer, module.model) == ("Trina", "TSM-NEG18C.20")
    assert {("peak_power_wp", 590.0), ("efficiency_pct", 22.8)} <= {
        (r.name, r.value) for r in module.readings}  # fmt: skip
    [inverter] = r2["inversor"].found
    assert (inverter.manufacturer, inverter.model) == ("Huawei", "SUN2000-20KTL-M5")
    [charger] = r2["carregamento_de_veiculos_eletricos"].found
    assert (charger.manufacturer, charger.reference) == ("MOREK", "MEV07DREWN6T2")
    assert r2["iluminacao_normal"].found[0].code == "L1/L5"
    assert not r2["quadros_eletricos"].found  # IP30 IK02 of every board: a requirement only
    assert {(n.param, n.value) for n in r2["quadros_eletricos"].needs} == {
        ("ip_rating", "IP30"), ("ik_rating", "IK02")}  # fmt: skip


# ---------------------------------------------------------------- the library in the database


@pytest.fixture
def seeded(db: Session, store: ObjectStore) -> dict[str, int]:
    if not HAVE_FIXTURES:
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))
    return seed_equipment(db)


def one(db: Session, **where: Any) -> Equipment:
    query = select(Equipment)
    for k, v in where.items():
        query = query.where(getattr(Equipment, k) == v)
    return db.scalars(query).one()


def test_the_library_is_proposed_from_both_ctes(db: Session, seeded: dict[str, int]) -> None:
    assert seeded["equipment"] > 60 and seeded["requirements"] > 20
    assert {e.status for e in db.scalars(select(Equipment))} == {"proposed"}
    portinhola = one(db, reference="+32470")
    assert (portinhola.category, portinhola.manufacturer) == ("portinhola", "Quitérios")
    assert portinhola.sources[0]["block_key"].endswith("entrada_de_energia")
    assert portinhola.sources[0]["entry"] is not None  # the block entry the slot points to
    box = one(db, model="317N")  # the same line in R1 and R2: one item, two sources
    assert sorted(s["project"] for s in box.sources) == ["R1", "R2"]
    l14 = one(db, code="L14")
    assert {(p.name, p.value, p.origin) for p in l14.params} >= {
        ("ip_rating", "IP65", "cte"), ("ik_rating", "IK10", "cte")}  # fmt: skip
    assert all(p.review_status == "extracted" for p in l14.params)


def test_requirements_belong_to_their_line_or_to_the_block(
    db: Session, seeded: dict[str, int]
) -> None:
    supply = db.scalars(select(Requirement).where(
        Requirement.block_key.endswith("entrada_de_energia"))).all()  # fmt: skip
    assert {(r.param_name, r.operator, r.value) for r in supply} == {
        ("ip_rating", ">=class", "IP55"), ("ik_rating", ">=class", "IK10"),
        ("icc_ka", ">=", 25.0)}  # fmt: skip
    assert all(r.equipment_id is None and r.status == "proposed" for r in supply)
    l14 = one(db, code="L14")
    own = db.scalars(select(Requirement).where(Requirement.equipment_id == l14.id)).all()
    assert {r.param_name for r in own} >= {"ip_rating", "ik_rating", "power_w"}


def test_an_illustration_goes_with_the_equipment_above_it(
    db: Session, seeded: dict[str, int]
) -> None:
    with_image = [e for e in db.scalars(select(Equipment)) if e.image]
    assert with_image, "as imagens de um só projeto passam a ser do equipamento"
    mirror = one(db, reference="43910 T BR")  # an image of R1 only (docs/fase4-diff-R1.md)
    assert mirror.image is not None and mirror.image["project"] == "R1"
    assert mirror.image["block_key"].endswith("espelhos")
    assert one(db, reference="43920 T BR").image != mirror.image  # each mirror its own


def test_seeding_again_keeps_the_curator_decisions(db: Session, seeded: dict[str, int]) -> None:
    portinhola = one(db, reference="+32470")
    portinhola.status, portinhola.name = "approved", "Portinhola (revista)"
    db.flush()

    again = seed_equipment(db)

    assert again == seeded
    assert one(db, reference="+32470").name == "Portinhola (revista)"


def test_the_library_keeps_no_personal_data(db: Session, seeded: dict[str, int]) -> None:
    known = _known_values()
    leaks = []
    for e in db.scalars(select(Equipment)):
        texts = [e.name, e.model or "", e.reference or ""] + [s["text"] for s in e.sources]
        texts += [p.text for p in e.params]
        for text in texts:
            bare = PLACEHOLDER.sub(" ", text)
            leaks += [(e.identity, h.kind) for h in privacy.find(bare)]
            folded = " ".join(bare.casefold().split())
            for key, value in known:
                v = " ".join(value.casefold().split())
                if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", folded):
                    leaks.append((e.identity, key))
    assert leaks == []
