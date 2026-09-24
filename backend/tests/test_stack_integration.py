"""Checks against the running docker compose stack (make up). Run with: pytest -m integration."""

import os
from pathlib import Path

import boto3
import httpx
import pytest
import redis
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    values.update({k: v for k, v in os.environ.items() if k in values})
    return values


ENV = _env()


def _port(name: str, default: str) -> str:
    return ENV.get(name) or default


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
