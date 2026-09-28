"""Screen E and the dashboard (Phase 5, task 5): coherence matrix, review gate, summary."""

from typing import Any

import pytest
from audit_projects import audited, validate
from conftest import Api

pytestmark = pytest.mark.usefixtures("inline_ingestion")
__all__ = ["audited"]

ROWS = ["Requerente", "Obra", "Localização (concelho)", "Tipo de utilização",
        "Potência a alimentar", "N.º de quadros", "N.º de carregadores VE", "Cabos principais",
        "Potência FV", "Dados do técnico"]  # fmt: skip


def row(state: dict[str, Any], label: str) -> dict[str, Any]:
    return next(r for r in state["matrix"]["rows"] if r["label"] == label)


def test_the_coherence_matrix_of_r2(audited: Any) -> None:
    _, state = audited("R2")
    matrix = state["matrix"]

    assert [c["id"] for c in matrix["columns"]] == [
        "MDJ", "CTE", "MQT_LPU", "FICHA_ELE", "IDENT_TERMO", "CALC", "DRAWINGS"]  # fmt: skip
    assert [r["label"] for r in matrix["rows"]] == ROWS
    assert matrix["reference"].startswith("ficha-base rev.")
    ev = row(state, "N.º de carregadores VE")
    assert ev["reference"] == "5" and ev["cells"]["CTE"] == {**ev["cells"]["CTE"], "value": "6",
                                                             "differs": True}  # fmt: skip
    assert ev["cells"]["MDJ"]["differs"] is False and ev["reading"] == "Erro provável no CTE."
    power = row(state, "Potência a alimentar")
    assert power["cells"]["FICHA_ELE"]["value"] == "180" and power["cells"]["FICHA_ELE"]["differs"]
    assert power["reading"] == "Erro provável na ficha eletrotécnica."
    requerente = row(state, "Requerente")
    assert requerente["reference"] == "•••"
    assert {c["value"] for c in requerente["cells"].values()} == {"•••"}
    assert requerente["cells"]["FICHA_ELE"]["differs"]


def test_r1_controls_are_coherent_in_the_matrix(audited: Any) -> None:
    _, state = audited("R1")

    assert row(state, "Potência a alimentar")["reading"] == "Coerente"
    boards = row(state, "N.º de quadros")
    assert boards["reading"] == "Coerente" and boards["reference"] == "6"
    assert {c["value"] for c in boards["cells"].values()} == {"6"}


def test_the_pieces_cannot_go_to_review_with_critical_issues_open(audited: Any, api: Api) -> None:
    project_id, state = audited("R2")
    client = api.as_("tecnico")

    refused = client.post(f"/api/projects/{project_id}/review-request", json={})
    critical = [i for i in state["issues"] if i["severity"] == "critical"]
    for issue in critical:
        client.post(f"/api/validation/issues/{issue['id']}/ignore",
                    json={"reason": "Confirmado com o técnico responsável."})  # fmt: skip
    sent = client.post(f"/api/projects/{project_id}/review-request", json={})

    assert refused.status_code == 409
    assert refused.json()["detail"]["open_critical"] == len(critical) > 0
    assert sent.status_code == 200 and sent.json()["sent"] == 2  # the MDJ and the CTE
    audit = [e["description"] for e in client.get(f"/api/projects/{project_id}/audit").json()]
    assert "Enviou 2 peças para revisão" in audit
    assert any(d.startswith("Ignorou um alerta COE-05: Confirmado") for d in audit)


def test_a_project_not_validated_cannot_go_to_review(audited: Any, api: Api) -> None:
    project = api.as_("redator").post("/api/projects", json={"code": "V1", "name": "V1"}).json()

    refused = api.as_("redator").post(f"/api/projects/{project['id']}/review-request", json={})

    assert refused.status_code == 409 and "Valide o projeto" in refused.json()["detail"]


def test_the_dashboard_shows_new_critical_issues_without_opening_the_project(
    audited: Any, api: Api
) -> None:
    project_id, state = audited("R2")

    listed = next(p for p in api.as_("redator").get("/api/projects").json()
                  if p["id"] == project_id)  # fmt: skip
    again = validate(api, project_id)
    relisted = next(p for p in api.as_("redator").get("/api/projects").json()
                    if p["id"] == project_id)  # fmt: skip

    critical = sum(1 for i in state["issues"] if i["severity"] == "critical")
    assert listed["validation"]["open_critical"] == listed["validation"]["new_critical"] == critical
    assert relisted["validation"]["new_critical"] == 0  # found again: not new
    assert again["run"]["totals"]["open_critical"] == critical
