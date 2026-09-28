"""Evaluation with the real LLM (SPEC 6.1): the adaptive blocks of R2 (PV, EV, SADI, audiovisual).

Optional and slow, with the key and the models of the .env: RUN_LLM_EVAL=1 pytest
(another provider for one run: LLM_PROVIDER=groq LLM_MODEL_DRAFTING=<model>, key in the .env)
backend/tests/llm_eval. Only data/fixtures reach the LLM (D5 pending). Automatic checks for each
case: valid JSON (the contract of SPEC 8.4), zero NUM-01, zero personal data sent (the privacy
guard finds nothing in the request, and the call is not blocked), and every placeholder is a
key of the ficha-base (or of the project's circuits and articles).
"""

import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from conftest import Api
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference_projects import load_confirmed, seed_library
from support import env

from app.assembly.values import ValueSource
from app.config import Settings
from app.drafting.draft import build_request, draft_section
from app.llm.client import LlmClient, make_provider
from app.llm.guard import PrivacyGuard, terms_for
from app.llm.ratelimit import MemoryRateLimiter
from app.models import FichaRevision, Project, Section, TemplateBlock
from app.storage import ObjectStore

pytestmark = [
    pytest.mark.usefixtures("inline_ingestion"),
    pytest.mark.skipif(not os.environ.get("RUN_LLM_EVAL"), reason="avaliação real: RUN_LLM_EVAL=1"),
]
PLACEHOLDER = re.compile(r"\{\{v:([a-z0-9_.]+)\}\}")
SADI = "ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi"
CASES = {
    "fotovoltaico": "ele.mdj.instalacao_fotovoltaica",
    "veiculos_eletricos": "ele.mdj.carregamento_de_veiculos_eletricos",
    "sadi": f"{SADI}.sadi",
    "matriz_de_incendio": f"{SADI}.matriz_de_incendio",
    "audiovisual": "ele.mdj.instalacao_audiovisual_auditorio",
}


def settings() -> Settings:
    values = env()
    provider = os.environ.get("LLM_PROVIDER") or values.get("LLM_PROVIDER") or "gemini"
    key = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
    model = os.environ.get("LLM_MODEL_DRAFTING") or values.get("LLM_MODEL_DRAFTING")
    if not values.get(key) or not model:
        pytest.skip(f"{key} e LLM_MODEL_DRAFTING no .env")
    return Settings(
        llm_provider=provider,
        gemini_api_key=values.get("GEMINI_API_KEY", ""),
        groq_api_key=values.get("GROQ_API_KEY", ""),
        llm_model_drafting=model,
        llm_rpm=int(values.get("LLM_RPM") or 8),
        llm_rpd=int(values.get("LLM_RPD") or 200),
    )


@pytest.fixture(scope="module")
def results() -> dict[str, dict[str, Any]]:
    return {}


@pytest.fixture
def r2(api: Api, db: Session, store: ObjectStore) -> dict[str, Any]:
    seed_library(db, store)
    project_id = load_confirmed(api, "R2", llm_allowed=True, resolve=True)
    doc = api.as_("redator").post(f"/api/projects/{project_id}/documents", json={"type": "MDJ"})
    assert doc.status_code == 201, doc.text
    return {"project_id": project_id, **doc.json()}


@pytest.mark.parametrize("case", list(CASES))
def test_adaptive_block_of_r2(
    case: str, api: Api, db: Session, r2: dict[str, Any], results: dict[str, dict[str, Any]]
) -> None:
    config = settings()
    key = CASES[case]
    row = next(s for s in r2["sections"] if s["block_key"] == key)
    assert row["active"], f"{key} não está ativo em R2"
    section = db.get(Section, uuid.UUID(row["id"]))
    project = db.get(Project, uuid.UUID(r2["project_id"]))
    assert section is not None and project is not None
    block = db.get(TemplateBlock, section.block_id)
    revision = db.get(FichaRevision, section.document.ficha_revision_id)
    assert block is not None and revision is not None
    values = ValueSource.load(db, revision)

    # zero personal data sent: the guard finds nothing in what would be sent
    body, _ = build_request(db, section, block, project, values)
    import json

    sent = json.dumps(body, ensure_ascii=False, default=str)
    assert PrivacyGuard(terms_for(db, project.id)).check({"pedido": sent}) == []

    limiter = MemoryRateLimiter(config.llm_rpm, config.llm_rpd)
    client = LlmClient(make_provider(config), limiter, config)
    version = draft_section(db, client, section)  # raises if the JSON is not valid twice

    [call] = client.calls
    assert call.status == "ok" and call.blocked == []
    num01 = [i for i in version.issues if i["rule"] == "NUM-01"]
    ref01 = [i for i in version.issues if i["rule"] == "REF-01"]
    text = " ".join(
        c.get("text", "") for n in version.content["content"] for c in n.get("content") or []
    )
    keys = {k["key"] for k in values.available()}
    used = {r.key for r in version.value_refs}
    unknown = sorted(k for k in used if k not in keys and values.resolve(k).missing)
    results[case] = {
        "num01": len(num01),
        "ref01": len(ref01),
        "unknown_keys": unknown,
        "tokens": (call.input_tokens, call.output_tokens),
        "ms": call.duration_ms,
        "attempts": call.attempts,
        "paragraphs": len(version.content["content"]),
    }
    print(f"\n[{case}] {results[case]}")
    assert num01 == [], [i["snippet"] for i in num01]
    assert unknown == [], f"marcadores que não existem na ficha: {unknown}"
    assert text.strip()
