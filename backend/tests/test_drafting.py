"""Drafting of the adaptive blocks (SPEC 8.4, Phase 4 task 4), with FakeProvider: no network."""

import json
import uuid
from typing import Any

import pytest
from conftest import Api
from fastapi import FastAPI
from reference_projects import load_confirmed, seed_library
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.drafting.jobs import draft_document, get_draft_queue, run_one
from app.llm.client import LlmClient
from app.llm.fake import FakeProvider, echo_first_source
from app.llm.provider import Message
from app.llm.ratelimit import MemoryRateLimiter
from app.models import BlockedTerm, LlmCall, Project, Section
from app.storage import ObjectStore

pytestmark = pytest.mark.usefixtures("inline_ingestion")
SETTINGS = Settings(llm_model_drafting="modelo-de-teste", llm_max_retries=1, llm_backoff_s=0)


class InlineDraftQueue:
    """Runs the drafting jobs at once, in the test transaction, as the worker would."""

    def __init__(self, db: Session, provider: FakeProvider, rpd: int = 1000) -> None:
        self.db, self.provider = db, provider
        self.limiter = MemoryRateLimiter(rpm=1000, rpd=rpd, sleep=lambda s: None)
        self.events: list[dict[str, Any]] = []

    def client(self) -> LlmClient:
        return LlmClient(self.provider, self.limiter, SETTINGS, sleep=lambda s: None)

    def publish(self, project_id: uuid.UUID, event: dict[str, Any]) -> None:
        self.events.append(event)

    def document(self, document_id: uuid.UUID) -> str:
        draft_document(self.db, self.client(), self.publish, document_id)
        return "job"

    def section(self, section_id: uuid.UUID, request: str | None) -> str:
        section = self.db.get(Section, section_id)
        assert section is not None
        run_one(self.db, self.client(), self.publish, section, section.document.project_id, request)
        return "job"


@pytest.fixture
def fake() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def drafts(app: FastAPI, db: Session, fake: FakeProvider) -> InlineDraftQueue:
    q = InlineDraftQueue(db, fake)
    app.dependency_overrides[get_draft_queue] = lambda: q
    return q


@pytest.fixture
def r1(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    allowed = api.as_("admin").patch(
        f"/api/projects/{project_id}/llm", json={"allowed": True, "reason": "Projeto das fixtures."}
    )
    assert allowed.status_code == 200
    doc = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
    return {"project_id": project_id, **doc.json()}


def section(doc: dict[str, Any], suffix: str) -> dict[str, Any]:
    return next(s for s in doc["sections"] if s["block_key"].endswith(suffix))


def versions(api: Api, section_id: str) -> list[dict[str, Any]]:
    return list(api.as_("redator").get(f"/api/sections/{section_id}/versions").json())


# ---------------------------------------------------------------- D5


def test_the_llm_is_on_by_default_and_off_only_by_the_admin(
    api: Api, db: Session, store: ObjectStore, drafts: InlineDraftQueue
) -> None:
    seed_library(db, store)
    project_id = load_confirmed(api, "R1")
    assert db.get(Project, project_id).llm_allowed is True  # type: ignore[union-attr]
    off = api.as_("admin").patch(
        f"/api/projects/{project_id}/llm",
        json={"allowed": False, "reason": "Cliente não autoriza."},
    )
    assert off.status_code == 200
    doc = (
        api.as_("redator")
        .post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
        .json()
    )

    response = api.as_("redator").post(f"/api/documents/{doc['id']}/generate")

    assert response.status_code == 409
    assert response.json()["detail"].startswith("LLM desligado neste projeto")
    assert drafts.provider.sent == []
    audit = api.as_("redator").get(f"/api/projects/{project_id}/audit").json()
    assert audit[-1]["description"] == "Pedido ao LLM recusado: LLM desligado neste projeto"


def test_only_an_admin_lets_a_project_use_the_llm(api: Api, r1: dict[str, Any]) -> None:
    body = {"allowed": False, "reason": "Teste."}
    assert (
        api.as_("tecnico").patch(f"/api/projects/{r1['project_id']}/llm", json=body).status_code
        == 403
    )
    assert api.as_("admin").patch(f"/api/projects/{r1['project_id']}/llm", json=body).json() == {
        "llm_allowed": False
    }


# ---------------------------------------------------------------- the request


def test_the_request_has_sources_keys_and_no_personal_data(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue
) -> None:
    intro = section(r1, "ele.mdj.introducao")

    assert api.as_("redator").post(f"/api/sections/{intro['id']}/generate").status_code == 202

    [(system, messages)] = drafts.provider.sent
    assert "Nunca escrevas números, nomes" in system
    body = json.loads(messages[0].text)
    assert [s["id"] for s in body["sources"]] == [
        "arc:R1:ele.mdj.introducao",
        "arc:R2:ele.mdj.introducao",
    ]
    keys = {k["key"] for k in body["keys"]}
    assert {"ele.potencia_alimentar_kva", "id.requerente.nome", "id.local.rua"} <= keys
    assert all(not c["key"].startswith("id.") for c in body["context_values"])
    assert "Bruno Exemplo" not in messages[0].text and "@" not in messages[0].text
    assert body["project"]["tipo"]["ele.classificacao"] == "Locais de habitação"


# ---------------------------------------------------------------- proposals


def test_the_agent_text_arrives_as_a_proposal(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue
) -> None:
    intro = section(r1, "ele.mdj.introducao")
    api.as_("redator").post(f"/api/sections/{intro['id']}/generate")

    [system_version, proposal] = versions(api, intro["id"])
    assert system_version["status"] == "current" and proposal["status"] == "proposed"
    assert proposal["author_type"] == "agent"
    generated = [
        n for n in proposal["content"]["content"] if (n.get("attrs") or {}).get("generated")
    ]
    assert generated and all(
        {"type": "generated"} in c["marks"] for n in generated for c in n["content"]
    )
    assert {c["target"] for c in proposal["citations"]} == {"arc:R1:ele.mdj.introducao"}
    doc = api.as_("redator").get(f"/api/documents/{r1['id']}").json()
    assert section(doc, "ele.mdj.introducao")["current_version"] == 1  # nothing replaced yet
    assert [e["status"] for e in drafts.events] == ["generating", "generated"]
    audit = [
        e["description"]
        for e in api.as_("redator").get(f"/api/projects/{r1['project_id']}/audit").json()
    ]
    assert "Propôs a versão 2 de «INTRODUÇÃO»" in audit


def test_accept_and_reject(api: Api, r1: dict[str, Any], drafts: InlineDraftQueue) -> None:
    intro = section(r1, "ele.mdj.introducao")
    api.as_("redator").post(f"/api/sections/{intro['id']}/generate")
    proposal = versions(api, intro["id"])[-1]

    accepted = api.as_("redator").post(f"/api/versions/{proposal['id']}/accept", json={}).json()

    assert accepted["status"] == "current"
    doc = api.as_("redator").get(f"/api/documents/{r1['id']}").json()
    now = section(doc, "ele.mdj.introducao")
    assert now["current_version"] == 2 and now["status"] in ("generated", "todo")
    assert (
        api.as_("redator").post(f"/api/versions/{proposal['id']}/reject", json={}).status_code
        == 409
    )
    api.as_("redator").post(f"/api/sections/{intro['id']}/requests", json={"text": "Mais conciso."})
    newest = versions(api, intro["id"])[-1]
    rejected = api.as_("redator").post(
        f"/api/versions/{newest['id']}/reject", json={"note": "Não."}
    )
    assert rejected.json()["status"] == "rejected"
    assert (
        section(api.as_("redator").get(f"/api/documents/{r1['id']}").json(), "ele.mdj.introducao")[
            "current_version"
        ]
        == 2
    )


def test_a_request_in_natural_language_uses_the_rewrite_prompt(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue
) -> None:
    intro = section(r1, "ele.mdj.introducao")

    api.as_("redator").post(
        f"/api/sections/{intro['id']}/requests", json={"text": "Reescreve para concurso público."}
    )

    system, messages = drafts.provider.sent[-1]
    assert "O técnico pede" in system
    body = json.loads(messages[0].text)
    assert body["request"] == "Reescreve para concurso público."
    assert "current_paragraphs" in body
    assert versions(api, intro["id"])[-1]["request"] == "Reescreve para concurso público."


def test_fixed_blocks_never_go_to_the_llm(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue
) -> None:
    fixed = section(r1, "quedas_de_tensao")
    response = api.as_("redator").post(
        f"/api/sections/{fixed['id']}/requests", json={"text": "Mais curto."}
    )
    assert response.status_code == 409 and "não passam pelo LLM" in response.json()["detail"]
    assert drafts.provider.sent == []


# ---------------------------------------------------------------- post-processing


def test_ref01_num01_and_missing_data(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue
) -> None:
    intro = section(r1, "ele.mdj.introducao")
    drafts.provider.responses = [
        json.dumps(
            {
                "block_key": "ele.mdj.introducao",
                "paragraphs": [
                    {
                        "id": "p1",
                        "text": "Moradia com {{v:ele.potencia_alimentar_kva}} kVA e 3 pisos.",
                        "sources": ["arc:R1:ele.mdj.introducao", "arc:R9:inventada"],
                    },
                    {
                        "id": "p2",
                        "text": "Localizada no lote {{v:id.local.nip}}, conforme a secção 801.5.",
                        "sources": [],
                    },
                ],
                "missing_data": ["ele.n_pisos", "ele.potencia_alimentar_kva", "número de pisos"],
                "assumptions": ["Moradia de 3 pisos (texto de R1)."],
            }
        )
    ]

    api.as_("redator").post(f"/api/sections/{intro['id']}/generate")

    proposal = versions(api, intro["id"])[-1]
    rules = [(i["rule"], i["paragraph"]) for i in proposal["issues"]]
    assert ("REF-01", "p1") in rules and ("NUM-01", "p1") in rules
    assert ("NUM-01", "p2") not in rules  # "secção 801.5" is in the whitelist
    # the power has a value: not missing; free text stays
    assert proposal["missing_data"] == ["ele.n_pisos", "número de pisos", "id.local.nip"]
    assert proposal["assumptions"] == ["Moradia de 3 pisos (texto de R1)."]
    assert {c["target"] for c in proposal["citations"]} == {"arc:R1:ele.mdj.introducao"}
    text = json.dumps(proposal["content"], ensure_ascii=False)
    assert "34,5" in text and "[falta: NIP]" in text


def test_invalid_answers_leave_the_section_todo(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue, db: Session
) -> None:
    intro = section(r1, "ele.mdj.introducao")
    drafts.provider.responses = ["não é JSON", '{"block_key": "x"}']

    api.as_("redator").post(f"/api/sections/{intro['id']}/generate")

    s = db.get(Section, uuid.UUID(intro["id"]))
    assert (
        s is not None
        and s.status == "todo"
        and (s.status_note or "").startswith("Resposta do LLM inválida")
    )
    assert drafts.events[-1]["status"] == "failed"
    assert len(versions(api, intro["id"])) == 1


def test_the_privacy_guard_blocks_before_sending(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue, db: Session
) -> None:
    db.add(BlockedTerm(value="Memória Descritiva", kind="name", source="admin"))  # in the sources
    db.flush()
    intro = section(r1, "ele.mdj.introducao")

    api.as_("redator").post(f"/api/sections/{intro['id']}/generate")

    assert drafts.provider.sent == []
    call = db.scalars(select(LlmCall)).one()
    assert (
        call.status == "blocked" and {"kind": "blocked_name", "where": "mensagem 1"} in call.blocked
    )
    assert "Memória Descritiva" not in (call.error or "")


# ---------------------------------------------------------------- the whole document


def test_the_document_is_drafted_and_a_stopped_run_resumes(
    api: Api, r1: dict[str, Any], drafts: InlineDraftQueue, db: Session
) -> None:
    drafts.limiter.rpd = 2  # the daily quota stops the first run after two sections

    api.as_("redator").post(f"/api/documents/{r1['id']}/generate")

    statuses = [e["status"] for e in drafts.events]
    assert statuses.count("generated") == 2 and statuses[-1] == "paused"
    drafts.limiter.rpd, drafts.limiter.days = 1000, {}
    drafts.events.clear()
    api.as_("redator").post(f"/api/documents/{r1['id']}/generate")
    drafted = {e["section_id"] for e in drafts.events if e["status"] == "generated"}
    active_adaptive = [
        s
        for s in r1["sections"]
        if s["active"] and any(n["type"] == "pending" for n in s["content"]["content"])
    ]
    assert len(drafted) == len(active_adaptive) - 2  # the first two are not drafted again


def test_the_fake_answers_the_contract() -> None:
    body = {"block_key": "k", "sources": [{"id": "arc:R1:k", "text": "Um.\nDois."}]}
    answer = json.loads(echo_first_source("", [Message("user", json.dumps(body))]))
    assert [p["text"] for p in answer["paragraphs"]] == ["Um.", "Dois."]
