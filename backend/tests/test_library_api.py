"""Curator API of the block library: evidence, preview, approve, reject, edit (Phase 3, task 5)."""

import re
from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from sqlalchemy.orm import Session

from app.ingest.detect import detect
from app.knowledge.sources import unique_files
from app.library import privacy
from app.library.seed import seed_blocks
from app.library.sources import seed_sources
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
PLACEHOLDER = re.compile(r"\{\{v:[a-z0-9_.]+\}\}")


@pytest.fixture
def seeded(db: Session, store: ObjectStore) -> None:
    if not (FIXTURES / "R1").is_dir() or not (FIXTURES / "R2").is_dir():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))


def blocks(api: Api, login: str = "redator", **params: str) -> list[dict[str, Any]]:
    response = api.as_(login).get("/api/library/blocks", params=params)
    assert response.status_code == 200
    return list(response.json())


def by_key(api: Api, suffix: str) -> dict[str, Any]:
    return next(b for b in blocks(api) if b["key"].endswith(suffix))


def test_empty_library(api: Api) -> None:
    assert blocks(api) == []


def test_everyone_reads_the_proposed_blocks(api: Api, seeded: None) -> None:
    mdj = blocks(api, "tecnico", doc_type="MDJ")

    assert len(mdj) == 42 and [b["order"] for b in mdj] == list(range(1, 43))
    assert {b["status"] for b in mdj} == {"proposed"}
    assert blocks(api, doc_type="CTE") == []
    rpc = by_key(api, "regulamento_dos_produtos_de_construcao_rpc")
    assert rpc["activation_rule"] == 'ele.classificacao != "Locais de habitação"'
    assert rpc["projects"] == ["R2"]


def test_detail_shows_the_evidence_side_by_side_without_personal_data(
    api: Api, seeded: None
) -> None:
    b = by_key(api, "ele.mdj.introducao")

    detail = api.as_("redator").get(f"/api/library/blocks/{b['id']}").json()

    assert set(detail["evidence"]) == {"R1", "R2"}
    adaptive = next(e for e in detail["entries"] if e["mode"] == "adaptive")
    r1 = [u["text"] for u in detail["evidence"]["R1"] if u["index"] in adaptive["units"]["R1"]]
    assert "{{v:id.local.rua}}" in r1[0]
    for units in detail["evidence"].values():
        for unit in units:
            bare = PLACEHOLDER.sub(" ", unit["text"])
            assert privacy.find(bare) == [] and "Exemplo" not in bare
    assert detail["archive_refs"] == ["arc:R1:ele.mdj.introducao", "arc:R2:ele.mdj.introducao"]


def test_placeholders_come_with_their_labels(api: Api, seeded: None) -> None:
    b = by_key(api, "ele.mdj.assinatura")

    detail = api.as_("redator").get(f"/api/library/blocks/{b['id']}").json()

    assert detail["labels"]["tec.nome"] == "Nome do técnico"
    assert detail["labels"]["doc.data"] == "Data (assinatura)"


@pytest.fixture
def r1_project(api: Api, seeded: None, inline_ingestion: None) -> str:
    project = api.as_("redator").post("/api/projects", json={"code": "R1", "name": "M"}).json()
    wanted = ("ficha_eletrotecnica", "calc_summary")
    files = [
        p for p in unique_files(FIXTURES / "R1") if detect(p.name, p.read_bytes()).kind in wanted
    ]
    assert len(files) == 2
    for path in files:
        response = api.as_("redator").post(
            f"/api/projects/{project['id']}/files", files={"file": (path.name, path.read_bytes())}
        )
        assert response.status_code == 202, response.text
    return str(project["id"])


def test_preview_with_the_ficha_of_a_project(api: Api, r1_project: str) -> None:
    supply = by_key(api, "alimentacao_de_energia")
    cover = by_key(api, "ele.mdj.capa")
    pv = by_key(api, "ele.mdj.instalacao_fotovoltaica")

    shown = (
        api.as_("redator")
        .get(f"/api/library/blocks/{supply['id']}/preview", params={"project_id": r1_project})
        .json()
    )
    power = next(p for p in shown["paragraphs"] if p["mode"] == "parametric")
    assert "potência elétrica de 34,5 kVA" in power["text"] and power["missing"] == []
    assert shown["active"] is True and shown["project_code"] == "R1"

    shown = (
        api.as_("redator")
        .get(f"/api/library/blocks/{cover['id']}/preview", params={"project_id": r1_project})
        .json()
    )
    requerente = next(p for p in shown["paragraphs"] if p["text"] and "REQUERENTE" in p["text"])
    assert requerente["text"] == "REQUERENTE: •••" and requerente["masked"] == [
        "id.requerente.nome"
    ]
    obra = next(p for p in shown["paragraphs"] if p["text"] and p["text"].startswith("OBRA"))
    assert obra["missing"] == ["id.obra.designacao"]  # not in the ficha eletrotécnica of R1
    assert obra["text"] == "OBRA: [falta: Designação da obra]"

    shown = (
        api.as_("redator")
        .get(f"/api/library/blocks/{pv['id']}/preview", params={"project_id": r1_project})
        .json()
    )
    assert shown["active"] is False  # no PV articles in R1
    assert [p["text"] for p in shown["paragraphs"]][1] is None  # adaptive: written in Phase 4


@pytest.mark.parametrize("login", ["redator", "tecnico", "admin"])
def test_only_a_curator_approves_rejects_or_edits(api: Api, seeded: None, login: str) -> None:
    b = by_key(api, "legislacao_e_normas")
    client = api.as_(login)

    assert (
        client.post(
            f"/api/library/blocks/{b['id']}/review", json={"decision": "approved"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/library/blocks/{b['id']}", json={"title": "X", "note": "abc"}
        ).status_code
        == 403
    )
    assert by_key(api, "legislacao_e_normas")["status"] == "proposed"


def test_curator_approves_and_it_is_in_the_history(api: Api, seeded: None) -> None:
    b = by_key(api, "legislacao_e_normas")

    response = api.as_("curador").post(
        f"/api/library/blocks/{b['id']}/review", json={"decision": "approved", "note": "Revisto."}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["reviewed_by"] == "dev:curador"
    [event] = api.as_("redator").get(f"/api/library/blocks/{b['id']}/history").json()
    assert event["description"] == "Aprovou o bloco «LEGISLAÇÃO E NORMAS» (MDJ)"
    assert event["actor_name"].startswith("Curador")


def test_editing_the_rule_checks_it_and_asks_for_a_new_approval(api: Api, seeded: None) -> None:
    b = by_key(api, "instalacao_fotovoltaica")
    api.as_("curador").post(f"/api/library/blocks/{b['id']}/review", json={"decision": "approved"})

    bad = api.as_("curador").patch(
        f"/api/library/blocks/{b['id']}",
        json={"activation_rule": "sys.fv", "note": "Mais simples."},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["position"] == 6
    assert "Falta a comparação" in bad.json()["detail"]["message"]

    good = api.as_("curador").patch(
        f"/api/library/blocks/{b['id']}",
        json={"activation_rule": 'sys.fv.present or any bom.chapter ~ "fotovoltaico"',
              "note": "Também pelo capítulo da LPU."},
    )  # fmt: skip
    assert good.status_code == 200
    assert good.json()["status"] == "proposed"  # edited: to be approved again
    history = api.as_("redator").get(f"/api/library/blocks/{b['id']}/history").json()
    assert [e["description"] for e in history] == [
        "Aprovou o bloco «INSTALAÇÃO FOTOVOLTAICA» (MDJ)",
        "Editou o bloco «INSTALAÇÃO FOTOVOLTAICA»: regra de ativação",
    ]
    same = api.as_("curador").patch(
        f"/api/library/blocks/{b['id']}",
        json={"activation_rule": 'sys.fv.present or any bom.chapter ~ "fotovoltaico"', "note": "x"},
    )
    assert same.status_code == 422


def test_unknown_block(api: Api) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert api.as_("redator").get(f"/api/library/blocks/{missing}").status_code == 404
    assert (
        api.as_("curador")
        .post(f"/api/library/blocks/{missing}/review", json={"decision": "approved"})
        .status_code
        == 404
    )
