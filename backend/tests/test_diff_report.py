"""Difference between the assembly of R1 and its original (Phase 4 acceptance, without the LLM)."""

import uuid

import pytest
from conftest import Api
from reference_projects import FIXTURES, have_fixtures, load_confirmed, seed_library
from sqlalchemy.orm import Session

from app.assembly.diff_report import build, compare_entry, markdown, value_kind
from app.config import Settings
from app.models import Document
from app.storage import ObjectStore

pytestmark = [
    pytest.mark.skipif(not have_fixtures(), reason="sem fixtures de R1"),
    pytest.mark.usefixtures("inline_ingestion"),
]


@pytest.fixture
def r1_documents(api: Api, db: Session, store: ObjectStore) -> list[Document]:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    out = []
    for doc_type in ("MDJ", "CTE"):
        created = api.as_("redator").post(
            f"/api/projects/{project_id}/documents", json={"type": doc_type}
        )
        document = db.get(Document, uuid.UUID(created.json()["id"]))
        assert document is not None
        out.append(document)
    return out


def test_r1_assembles_with_no_unexplained_defect(
    db: Session, settings: Settings, r1_documents: list[Document]
) -> None:
    reports = [build(db, settings, d, FIXTURES, "R1") for d in r1_documents]
    text = markdown(reports)

    for report in reports:
        assert report.count("defect") == 0, [d for d in report.differences if d.cls == "defect"]
        assert report.equal > 0 and report.count("adaptive") > 0
    mdj, cte = reports
    assert [k[0] for k in mdj.known] == ["C1"] and [k[0] for k in cte.known] == ["C2"]
    kinds = {d.kind for d in mdj.differences}
    assert {"perfil do técnico", "data pelo técnico (P8)", "índice"} <= kinds
    # never a personal value: the development technician's name and the fixtures' emails
    assert "Técnico de Desenvolvimento" not in text and "@" not in text


def test_a_changed_literal_is_a_defect_and_values_are_classified() -> None:
    class Values:
        def resolve(self, key: str) -> object:
            from app.assembly.values import Resolved

            return Resolved(key, {"ele.potencia_alimentar_kva": "34,5"}.get(key))

    template = "Potência a alimentar: {{v:ele.potencia_alimentar_kva}} kVA."
    same, diffs = compare_entry(template, "Potência a alimentar: 34,50 kVA.", Values())  # type: ignore[arg-type]
    assert same and diffs == [("ele.potencia_alimentar_kva", "34,50", "34,5", False)]
    assert value_kind(*diffs[0])[0] == "formato do número"
    changed, _ = compare_entry(template, "Potência instalada: 34,5 kVA.", Values())  # type: ignore[arg-type]
    assert not changed
    assert value_kind("id.local.concelho", "COIMBRA", "Coimbra", False)[0] == "maiúsculas"
    assert "não mostrado" in value_kind("id.requerente.nome", "A", "B", True)[1]
