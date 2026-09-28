"""The rules of SPEC 9 on R1 and R2 loaded as audits (Phase 5, task 4): every case of Annex C with
its likely reading, the controls without alerts, and no personal value in any issue."""

import json
import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from audit_projects import load_audit, validate
from conftest import Api, Published, RecordingQueue
from reference_projects import FIXTURES, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.knowledge.seed import seed_knowledge
from app.models import FichaValue, PieceFacts, ProjectFile, RegulationDoc
from app.storage import ObjectStore
from app.validation.engine import run_validation

pytestmark = pytest.mark.usefixtures("inline_ingestion")


@pytest.fixture
def audited(
    api: Api, db: Session, store: ObjectStore, settings: Settings, published: Published,
    validation_queue: RecordingQueue,
) -> Any:  # fmt: skip
    def run(run_id: uuid.UUID) -> None:
        run_validation(db, store, settings, published, run_id)

    validation_queue.run = run
    seed_library(db, store)
    seed_knowledge(db, FIXTURES)

    def load(code: str, *, public: bool = False) -> tuple[str, dict[str, Any]]:
        project_id = load_audit(api, code, public=public)
        return project_id, validate(api, project_id)

    return load


def issues(state: dict[str, Any], rule: str, *words: str) -> list[dict[str, Any]]:
    return [i for i in state["issues"] if i["rule_id"] == rule
            and all(w in i["message"] for w in words)]  # fmt: skip


def one(state: dict[str, Any], rule: str, *words: str) -> dict[str, Any]:
    found = issues(state, rule, *words)
    assert len(found) == 1, (rule, words, [i["message"] for i in issues(state, rule)])
    return found[0]


def assert_no_personal_values(db: Session, project_id: str, state: dict[str, Any]) -> None:
    shown = json.dumps(state, ensure_ascii=False).lower()
    personal = {str(v).lower() for v in db.scalars(select(FichaValue.value).where(
        FichaValue.personal_data.is_(True))) if isinstance(v, str) and len(v) > 5}  # fmt: skip
    for cached in db.scalars(select(PieceFacts).where(PieceFacts.project_id == project_id)):
        personal |= {str(f["value"]).lower() for f in cached.data["facts"]
                     if f["personal"] and len(str(f["value"])) > 5}  # fmt: skip
    assert personal
    assert not [v for v in personal if v in shown]


def test_r1_annex_c_and_the_controls(audited: Any, db: Session) -> None:
    project_id, state = audited("R1")

    c1 = one(state, "COE-06", "MDJ (existente) indica H07V-K")
    assert c1["severity"] == "critical" and c1["likely_reading"] == "Erro provável na MDJ."
    c2 = one(state, "TIP-01", "«apartamento»")
    assert "Videoporteiro" in c2["message"]
    assert c2["likely_reading"] == "Texto herdado de outro projeto."
    c3 = one(state, "COE-04", "n.º de membro OET")
    assert c3["likely_reading"] == "Confirmar com o perfil do técnico."
    assert {v["value"] for v in c3["evidence"]["values"]} == {"•••"}
    assert sorted(map(sorted, c3["evidence"]["groups"])) == [
        ["CTE (existente)", "MDJ (existente)"], ["Identificação", "Termo"]]  # fmt: skip
    c4 = one(state, "DES-01")
    assert "17 folhas" in c4["message"] and "16 páginas" in c4["message"]
    assert c4["likely_reading"] == "Folha em falta no PDF ou índice desatualizado."
    assert one(state, "TXT-01", "«45070 S»")["severity"] == "info"  # C5
    assert not issues(state, "CCP-01")  # R1 is not public procurement
    assert one(state, "TXT-01", "quase iguais", "Normas portuguesas")  # C14
    # controls: 34,5 kVA and 6 boards everywhere
    assert not issues(state, "COE-05")
    assert not issues(state, "COE-01")
    assert_no_personal_values(db, project_id, state)


def test_r2_annex_c(audited: Any, db: Session) -> None:
    project_id, state = audited("R2")

    c6 = one(state, "COE-05")
    assert "Ficha eletrotécnica 180 kVA" in c6["message"] and "(200 kVA)" in c6["message"]
    assert c6["likely_reading"] == "Erro provável na ficha eletrotécnica."
    assert one(state, "CNT-01", "MDJ (existente): não indica a potência")
    c7 = one(state, "COE-04", "(requerente)", "Ficha eletrotécnica")
    assert c7["likely_reading"].startswith("Ficha eletrotécnica reaproveitada de outro projeto")
    assert {v["value"] for v in c7["evidence"]["values"]} == {"•••"}
    c7_use = one(state, "TIP-01", "«Escritório»")
    assert c7_use["likely_reading"].startswith("Ficha eletrotécnica reaproveitada")
    c8 = one(state, "COE-01", "carregadores")
    assert "CTE (existente) 6" in c8["message"] and c8["severity"] == "critical"
    assert c8["likely_reading"] == "Erro provável no CTE."
    assert any("3 \u00d7 2" in (v["note"] or "") for v in c8["evidence"]["values"])
    c9 = [i for i in issues(state, "COE-06")
          if "FXZ1" in i["message"] or "XZ1(frt,zh)" in i["message"]]  # fmt: skip
    assert len(c9) == 2 and {i["likely_reading"] for i in c9} == {"Pedir equivalência ao curador."}
    assert all(i["severity"] == "warning" and "ask_curator" in i["actions"] for i in c9)
    c10 = one(state, "CAL-01", "Portinhola → Q.E.G.", "I2 ≤ 1,45·Iz")
    assert "I2 = 504 A" in c10["message"]
    assert c10["likely_reading"] == "Confirmar na folha de cálculo."
    assert len(issues(state, "REF-03")) == 3  # C11: MDJ twice, CTE once
    c12 = one(state, "COE-03", "MDJ (existente)", "Canalizações Enterradas")
    assert c12["likely_reading"] == "Bloco em falta na MDJ."
    assert issues(state, "TXT-01", "quebra de linha a meio de frase")  # C13
    assert_no_personal_values(db, project_id, state)


def test_ccp_01_in_public_procurement_c5(audited: Any) -> None:
    _, state = audited("R1", public=True)

    found = issues(state, "CCP-01")

    assert any("Videoporteiro" in i["message"] for i in found)
    assert all(i["severity"] == "warning" for i in found)


# ---------------------------------------------------------------- branches with no Annex C case


def test_coe_02_a_file_newer_than_the_ficha_proposes_to_update_the_ficha(
    audited: Any, db: Session, api: Api
) -> None:
    project_id, _ = audited("R2")
    fe = db.scalars(
        select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.kind == "ficha_eletrotecnica"
        )
    ).one()
    fe.file_date = date.today() + timedelta(days=3)
    db.commit()

    state = validate(api, project_id)

    found = issues(state, "COE-02", "Ficha eletrotécnica")
    assert found and all("propor atualizar a ficha" in i["likely_reading"] for i in found)
    c6 = one(state, "COE-05")
    assert c6["likely_reading"].startswith("Ficha eletrotécnica é mais recente")


def test_ref_02_a_revoked_document_is_critical(audited: Any, db: Session, api: Api) -> None:
    project_id, first = audited("R1")
    assert issues(first, "REF-02") and {i["severity"] for i in issues(first, "REF-02")} == {"info"}
    rtiebt = db.scalars(select(RegulationDoc).where(RegulationDoc.code == "rtiebt")).one()
    rtiebt.status = "revoked"
    db.commit()

    state = validate(api, project_id)

    revoked = [i for i in issues(state, "REF-02") if i["severity"] == "critical"]
    assert revoked and all("revogado" in i["message"] for i in revoked)
