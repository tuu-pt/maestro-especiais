"""
Phase 1 acceptance with the anonymized reference projects (SPEC section 14, Annex C).

Skipped with a warning while data/fixtures/R1 and R2 do not exist: the phase only closes
when these pass. Files are found by content (the anonymizer may rename them).
"""

from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import ficha_eletrotecnica, tabela_calculo
from app.ingest.detect import detect
from app.models import CircuitSheet, FichaConflict

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


@pytest.mark.parametrize("code", ["R1", "R2"])
def test_both_readers_read_the_power_without_warnings(code: str) -> None:
    """Without this, an agreement could only mean that one source gave nothing."""
    files = reference_files(code)
    fe_read = ficha_eletrotecnica.read(files["ficha_eletrotecnica"].read_bytes())
    calc_read = tabela_calculo.read(files["calc_summary"].read_bytes())
    for result in (fe_read, calc_read):
        assert result.warnings == []
        assert POWER in {c.key for c in result.values}


def test_r1_control_power_agrees_between_sources(api: Api) -> None:
    """Control case of Annex C: 34,5 kVA in the ficha eletrotécnica and in the Tabela."""
    body = load(api, "R1")
    power = value(body, POWER)
    assert power["status"] != "conflict", power
    assert power["value"] == 34.5
    assert body["circuits"], "a Tabela de Cálculo de R1 tem troços"
    assert body["open_conflicts"] == 0, "casos de controlo não podem gerar alertas"


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


# ---------------------------------------------------------------- Phase 2: 09-Folhas


def load_with_sheets(api: Api, db: Session, code: str) -> dict[str, list[Any]]:
    """Tabela + every 09-Folha of the project; conflicts per "destination field"."""
    reference_files(code)  # skips when the fixtures are missing
    client = api.as_("redator")
    project_id = client.post("/api/projects", json={"code": code, "name": code}).json()["id"]
    tabela = next(
        p
        for p in (FIXTURES / code).rglob("*.xlsx")
        if detect(p.name, p.read_bytes()).kind == "calc_summary"
    )
    sheets = sorted((FIXTURES / code).rglob("*.xls"))
    for path in [tabela, *sheets]:
        response = client.post(
            f"/api/projects/{project_id}/files", files={"file": (path.name, path.read_bytes())}
        )
        assert response.status_code == 202, response.text
    listed = client.get(f"/api/projects/{project_id}/files").json()
    assert {f["ingest_status"] for f in listed} == {"done"}, listed
    rows = db.scalars(select(FichaConflict).where(FichaConflict.circuit_id.is_not(None)))
    return {
        f"{c.circuit.destination if c.circuit else None} {c.field}": [
            x["value"] for x in c.candidates
        ]
        for c in rows
    }


def test_r1_sheets_agree_with_the_tabela_except_one_voltage_drop(api: Api, db: Session) -> None:
    """Control case (decision of 24 Sep 2026): only Q.E.G. → Q.P.1.2 differs, 0,9 % vs 0,76 %."""
    conflicts = load_with_sheets(api, db, "R1")
    assert list(conflicts) == ["Q.P.1.2 vd_section_pct"]
    tabela, sheet = conflicts["Q.P.1.2 vd_section_pct"]
    assert tabela == 0.9 and round(sheet, 2) == 0.76
    links = {s.link_status for s in db.scalars(select(CircuitSheet))}
    assert links == {"rule"}  # the 6 sheets found their circuit by file name


def test_r2_sheets_show_the_real_divergences(api: Api, db: Session) -> None:
    conflicts = load_with_sheets(api, db, "R2")
    assert {"Q.E.G. in_a", "Q.E.G. i2_a", "Q.E.G. length_m", "Q.AVAC i2_a"} <= set(conflicts)
    assert conflicts["Q.E.G. in_a"] == [315, 250]
    assert conflicts["Q.AVAC i2_a"] == [290, 42]
    unlinked = [s for s in db.scalars(select(CircuitSheet)) if s.link_status == "unlinked"]
    assert [(s.origin_hint, s.destination_hint) for s in unlinked] == [("QPEXT", "CVE")]
