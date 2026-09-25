"""A reference project (R1, R2) loaded through the API, with its ficha-base confirmed.

For the Phase 4 tests: the files are found by content in data/fixtures, uploaded as a person
would, read inline, and the revision is confirmed by the technician (it must have no conflicts).
"""

from pathlib import Path

import pytest
from conftest import Api
from sqlalchemy.orm import Session

from app.ingest.detect import detect
from app.knowledge.sources import unique_files
from app.library.seed import seed_blocks
from app.library.sources import seed_sources
from app.storage import ObjectStore

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"
PHASE4_KINDS = ("ficha_eletrotecnica", "calc_summary", "mqt", "lpu")


def have_fixtures() -> bool:
    return (FIXTURES / "R1").is_dir() and (FIXTURES / "R2").is_dir()


def seed_library(db: Session, store: ObjectStore) -> None:
    seed_sources(db, store, FIXTURES, ("R1", "R2"))
    seed_blocks(db, FIXTURES, ("R1", "R2"))


def files_of(code: str, kinds: tuple[str, ...] = PHASE4_KINDS) -> list[Path]:
    found: dict[str, Path] = {}
    for path in unique_files(FIXTURES / code):
        kind = detect(path.name, path.read_bytes()).kind
        if kind in kinds:
            found.setdefault(kind, path)  # one file of each kind (R1 has the MQT twice)
    return list(found.values())


def load_confirmed(api: Api, code: str, *, llm_allowed: bool = False) -> str:
    """Project id of the reference project, ficha-base confirmed."""
    if not have_fixtures():
        pytest.skip("data/fixtures/R1 e R2 são precisos")
    client = api.as_("redator")
    project = client.post("/api/projects", json={"code": code, "name": f"{code} (fixtures)"}).json()
    for path in files_of(code):
        response = client.post(
            f"/api/projects/{project['id']}/files", files={"file": (path.name, path.read_bytes())}
        )
        assert response.status_code == 202, response.text
    ficha = client.get(f"/api/projects/{project['id']}/ficha").json()
    assert ficha["open_conflicts"] == 0, f"{code}: conflitos por resolver na ficha-base"
    confirmed = api.as_("tecnico").post(f"/api/ficha/revisions/{ficha['revision']['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    return str(project["id"])
