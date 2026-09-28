"""A reference project loaded as an audit (Phase 5): every piece, including the MDJ, the CTE, the
identification and the term made by hand, the ficha-base confirmed, then validated.

The conflicts of the ficha-base are resolved as the technician did in the approved project: the
Tabela de Cálculo first (C6: 200 kVA), then the MQT/LPU (C7: the requerente of the LPU), then the
ficha eletrotécnica, then the drawings (whose personal fields the anonymizer scrambled in R1).
The cases themselves are what the validation finds.
"""

from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from reference_projects import FIXTURES, have_fixtures

from app.ingest.detect import detect

AUDIT_KINDS = ("ficha_eletrotecnica", "calc_summary", "mqt", "lpu", "drawing_pdf", "mdj_docx",
               "cte_docx", "identificacao_docx", "termo_docx")  # fmt: skip
SOURCE_ORDER = ("calc", "mqt", "ficha_eletrotecnica", "drawing", "manual")
BUILDING = {"R1": "Moradia unifamiliar", "R2": "Biblioteca"}


def _stale(path: Path) -> bool:
    """Old versions and signed or duplicated copies are not the pieces of the project."""
    return any(w in str(path).lower() for w in ("/old/", "signed", "(1)"))


def audit_files(code: str) -> list[Path]:
    found: dict[str, Path] = {}
    paths = sorted((FIXTURES / code).rglob("*"), key=lambda p: (_stale(p), str(p)))
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in (".xlsx", ".xlsm", ".pdf", ".docx"):
            continue
        kind = detect(path.name, path.read_bytes()).kind
        if kind in AUDIT_KINDS:
            found.setdefault(kind, path)
    return list(found.values())


def resolve_by_source(api: Api, project_id: str) -> int:
    ficha = api.as_("redator").get(f"/api/projects/{project_id}/ficha").json()
    resolved = 0
    for group in ficha["groups"]:
        for value in group["values"]:
            conflict = value.get("conflict")
            if not conflict:
                continue
            kinds = [c["source_type"] for c in conflict["candidates"]]
            index = min(range(len(kinds)), key=lambda i: SOURCE_ORDER.index(kinds[i])
                        if kinds[i] in SOURCE_ORDER else 99)  # fmt: skip
            response = api.as_("tecnico").post(
                f"/api/ficha/conflicts/{conflict['id']}/resolve",
                json={"candidate": index, "note": "Como no projeto aprovado (auditoria)."},
            )
            assert response.status_code == 200, response.text
            resolved += 1
    return resolved


def load_audit(api: Api, code: str, *, public: bool = False) -> str:
    if not have_fixtures():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    client = api.as_("redator")
    project = client.post("/api/projects", json={
        "code": f"{code}-AUD", "name": f"{code} (auditoria)", "building_type": BUILDING[code],
        "public_procurement": public,
    }).json()  # fmt: skip
    for path in audit_files(code):
        response = client.post(
            f"/api/projects/{project['id']}/files", files={"file": (path.name, path.read_bytes())}
        )
        assert response.status_code == 202, response.text
    resolve_by_source(api, str(project["id"]))
    ficha = client.get(f"/api/projects/{project['id']}/ficha").json()
    assert ficha["open_conflicts"] == 0
    confirmed = api.as_("tecnico").post(f"/api/ficha/revisions/{ficha['revision']['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    return str(project["id"])


def validate(api: Api, project_id: str) -> dict[str, Any]:
    started = api.as_("redator").post(f"/api/projects/{project_id}/validation", json={})
    assert started.status_code == 202, started.text
    state: dict[str, Any] = api.as_("redator").get(f"/api/projects/{project_id}/validation").json()
    assert state["run"] is not None and state["run"]["status"] == "done", state["current"]
    return state
