"""
Phase 1 acceptance with the anonymized reference projects (SPEC section 14, Annex C).

Skipped with a warning while data/fixtures/R1 and R2 do not exist: the phase only closes
when these pass. Files are found by content (the anonymizer may rename them).
"""

from pathlib import Path
from typing import Any

import pytest
from conftest import Api

from app.ingest.detect import detect

pytestmark = pytest.mark.usefixtures("inline_ingestion")

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures"
POWER = "ele.potencia_alimentar_kva"


def reference_files(code: str) -> dict[str, Path]:
    """The ficha eletrotécnica and the Tabela de Cálculo of a reference project."""
    root = FIXTURES / code
    if not root.is_dir():
        pytest.skip(f"data/fixtures/{code} não existe: anonimizar {code} para fechar a Fase 1")
    found: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".xlsx", ".xlsm"}:
            kind = detect(path.name, path.read_bytes()).kind
            found.setdefault(kind, []).append(path)
    missing = [k for k in ("ficha_eletrotecnica", "calc_summary") if len(found.get(k, [])) != 1]
    if missing:
        counts = {k: len(found.get(k, [])) for k in ("ficha_eletrotecnica", "calc_summary")}
        pytest.fail(f"{code}: esperado um ficheiro de cada tipo, encontrado {counts}")
    return {k: found[k][0] for k in ("ficha_eletrotecnica", "calc_summary")}


def load(api: Api, code: str) -> dict[str, Any]:
    files = reference_files(code)
    client = api.as_("redator")
    project_id = client.post("/api/projects", json={"code": code, "name": code}).json()["id"]
    for path in files.values():
        response = client.post(
            f"/api/projects/{project_id}/files", files={"file": (path.name, path.read_bytes())}
        )
        assert response.status_code == 202, response.text
    listed = client.get(f"/api/projects/{project_id}/files").json()
    assert [f["ingest_status"] for f in listed] == ["done", "done"], listed
    body: dict[str, Any] = client.get(f"/api/projects/{project_id}/ficha").json()
    return body


def value(body: dict[str, Any], key: str) -> dict[str, Any]:
    found: dict[str, Any] = next(v for g in body["groups"] for v in g["values"] if v["key"] == key)
    return found


def test_r1_control_power_agrees_between_sources(api: Api) -> None:
    """Control case of Annex C: 34,5 kVA in the ficha eletrotécnica and in the Tabela."""
    body = load(api, "R1")
    power = value(body, POWER)
    assert power["status"] != "conflict", power
    assert power["value"] == 34.5
    assert body["circuits"], "a Tabela de Cálculo de R1 tem troços"


def test_r2_c6_power_is_a_conflict(api: Api) -> None:
    """C6: ficha eletrotécnica 180 kVA, Tabela de Cálculo 200 kVA; nothing is chosen."""
    body = load(api, "R2")
    power = value(body, POWER)
    assert power["status"] == "conflict"
    assert power["value"] is None
    candidates = {c["source_type"]: c["value"] for c in power["conflict"]["candidates"]}
    assert candidates == {"ficha_eletrotecnica": 180, "calc": 200}
    assert body["can_confirm"] is False


def test_r2_c10_entry_circuit_fails_i2(api: Api) -> None:
    """C10: Portinhola → Q.E.G. with I2 = 504 A and 1,45·Iz = 503,4 A."""
    body = load(api, "R2")
    entry = next(c for c in body["circuits"] if "portinhola" in (c["origin"] or "").casefold())
    assert entry["cal01"]["i2_iz145"] == "fail"
