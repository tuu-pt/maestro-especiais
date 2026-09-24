"""Checks against the running docker compose stack (make up). Run with: pytest -m integration."""

import os

import boto3
import httpx
import pytest
import redis
from sqlalchemy import create_engine, text
from support import env, port

pytestmark = pytest.mark.integration

ENV = env()


def _port(name: str, default: str) -> str:
    return port(ENV, name, default)


def test_health_endpoint_reports_every_service_ok() -> None:
    response = httpx.get(f"http://localhost:{_port('BACKEND_HOST_PORT', '8000')}/api/health")

    assert response.status_code == 200, response.text
    services = response.json()["services"]
    assert {name: s["status"] for name, s in services.items()} == {
        "database": "ok",
        "pgvector": "ok",
        "redis": "ok",
        "storage": "ok",
    }


def _db_url() -> str:
    return (
        f"postgresql+psycopg://{ENV['POSTGRES_USER']}:{ENV['POSTGRES_PASSWORD']}"
        f"@localhost:{_port('DB_HOST_PORT', '55432')}/{ENV['POSTGRES_DB']}"
    )


def test_pgvector_computes_distances() -> None:
    engine = create_engine(_db_url())
    with engine.connect() as conn:
        distance = conn.execute(text("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")).scalar()
    engine.dispose()

    assert distance == pytest.approx(1.0)


def test_portuguese_text_search_is_available() -> None:
    engine = create_engine(_db_url())
    with engine.connect() as conn:
        matches = conn.execute(
            text(
                "SELECT to_tsvector('portuguese', 'instalações elétricas') "
                "@@ to_tsquery('portuguese', 'instalação')"
            )
        ).scalar()
    engine.dispose()

    assert matches is True


def test_redis_requires_password_and_answers_ping() -> None:
    port = int(_port("REDIS_HOST_PORT", "56379"))

    with pytest.raises(redis.AuthenticationError):
        redis.Redis(host="localhost", port=port).ping()
    assert redis.Redis(host="localhost", port=port, password=ENV["REDIS_PASSWORD"]).ping()


def test_bucket_exists() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=f"http://localhost:{_port('S3_HOST_PORT', '59000')}",
        aws_access_key_id=ENV["S3_ACCESS_KEY"],
        aws_secret_access_key=ENV["S3_SECRET_KEY"],
        region_name="us-east-1",
    )

    client.head_bucket(Bucket=ENV.get("S3_BUCKET") or "maestro-especiais")


@pytest.mark.skipif(
    not os.environ.get("RUN_INGEST_E2E"),
    reason="creates data in the development database: runs in CI (RUN_INGEST_E2E=1)",
)
def test_worker_reads_uploads_and_opens_a_conflict() -> None:
    import time
    import uuid

    import factories

    base = f"http://localhost:{_port('BACKEND_HOST_PORT', '8000')}/api"
    client = httpx.Client(base_url=base, headers={"X-Dev-User": "redator"}, timeout=30)
    code = f"CI{uuid.uuid4().hex[:8].upper()}"
    project = client.post("/projects", json={"code": code, "name": "Integração"}).json()
    rows = [list(r) for r in factories.CALC_ROWS]
    rows[1][2] = 200
    for name, data in (
        ("FE.xlsm", factories.ficha_eletrotecnica(R29=180)),
        ("Tabela.xlsx", factories.tabela_calculo(rows=rows)),
    ):
        response = client.post(f"/projects/{project['id']}/files", files={"file": (name, data)})
        assert response.status_code == 202, response.text

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        files = client.get(f"/projects/{project['id']}/files").json()
        if all(f["ingest_status"] in ("done", "failed") for f in files):
            break
        time.sleep(1)
    assert [f["ingest_status"] for f in files] == ["done", "done"], files
    ficha = client.get(f"/projects/{project['id']}/ficha").json()
    assert ficha["open_conflicts"] == 1
