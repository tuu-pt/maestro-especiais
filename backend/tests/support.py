"""Test helpers: local .env values and the test database URL."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def env() -> dict[str, str]:
    """Values from the repository .env, overridden by the process environment."""
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


def port(values: dict[str, str], name: str, default: str) -> str:
    return values.get(name) or default


def test_database_url() -> str:
    """TEST_DATABASE_URL, or the maestro_test database on the compose Postgres."""
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    values = env()
    user, password = values.get("POSTGRES_USER"), values.get("POSTGRES_PASSWORD")
    if not user or not password:
        raise RuntimeError("Sem credenciais do Postgres: corra `make env` e `make up`.")
    host_port = port(values, "DB_HOST_PORT", "55432")
    return f"postgresql+psycopg://{user}:{password}@localhost:{host_port}/maestro_test"
