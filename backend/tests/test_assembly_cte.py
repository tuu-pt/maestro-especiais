"""CTE of R1 assembled from its confirmed ficha-base (Phase 4, task 2)."""

import io
import zipfile
from typing import Any

import docx
import pytest
from conftest import Api
from reference_projects import load_confirmed, seed_library
from sqlalchemy.orm import Session
from test_assembly_mdj import _assert_package_is_whole

from app.storage import ObjectStore

pytestmark = pytest.mark.usefixtures("inline_ingestion")
SPECIAL = "ele.cte.condicoes_tecnicas_especiais"


@pytest.fixture
def cte(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    response = api.as_("redator").post(
        f"/api/projects/{project_id}/documents", json={"type": "CTE"}
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def by_key(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["block_key"]: s for s in doc["sections"]}


def test_the_cte_of_r1_follows_the_library(cte: dict[str, Any]) -> None:
    sections = by_key(cte)

    assert cte["type"] == "CTE" and len(cte["sections"]) == 53
    # systems R1 does not have: KNX, PV, SADI, EV, audiovisual
    for key in ("servidor_knx", "inversor", "sistema_de_alarme_e_detecao_de_incendio_sadi",
                "carregamento_de_veiculos_eletricos", "sistema_audiovisual"):  # fmt: skip
        s = sections[f"{SPECIAL}.{key}"]
        assert not s["active"] and s["active_reason"], key
    assert "KNX" in sections[f"{SPECIAL}.servidor_knx"]["active_reason"]
    # what R1 has: the videoporteiro of its MQT
    assert sections[f"{SPECIAL}.videoporteiro"]["active"]


def test_general_conditions_are_locked(cte: dict[str, Any]) -> None:
    general = [
        s
        for s in cte["sections"]
        if s["block_key"].startswith("ele.cte.condicoes_tecnicas_gerais.")
    ]

    fixed = [s for s in general if s["mode"] == "fixed"]
    assert len(fixed) == 3 and all(s["locked"] and s["status"] == "generated" for s in fixed)


def test_equipment_slots_are_empty_and_marked_for_phase_7(cte: dict[str, Any]) -> None:
    slots = [slot for s in cte["sections"] for slot in s["equipment_slots"]]

    assert slots
    assert all(slot["phase"] == 7 and slot["equipment"] is None for slot in slots)
    assert all(s["equipment_slots"] == [] for s in cte["sections"] if s["kind"] != "block")


def test_draft_of_the_cte_is_whole(api: Api, cte: dict[str, Any]) -> None:
    response = api.as_("redator").get(f"/api/documents/{cte['id']}/draft.docx")

    assert response.status_code == 200
    package = zipfile.ZipFile(io.BytesIO(response.content))
    _assert_package_is_whole(package)
    document = docx.Document(io.BytesIO(response.content))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "CONDIÇÕES TÉCNICAS" in text.upper()
    assert "Servidor KNX" not in text  # inactive sections are left out
    assert len(document.inline_shapes) > 10  # the pictures of the tubes, boxes, sockets…
