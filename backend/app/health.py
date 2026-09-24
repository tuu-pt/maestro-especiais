from collections.abc import Callable
from functools import lru_cache
from typing import Literal

import redis
from pydantic import BaseModel
from sqlalchemy import Engine, create_engine, text

from app.config import Settings, get_settings
from app.storage import make_s3_client

# A check returns normally when the service is healthy and raises otherwise.
ServiceCheck = Callable[[], None]


class ServiceStatus(BaseModel):
    status: Literal["ok", "error"]
    # Only the exception type: messages can carry connection strings or credentials.
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    services: dict[str, ServiceStatus]


def run_checks(checks: dict[str, ServiceCheck]) -> HealthResponse:
    services: dict[str, ServiceStatus] = {}
    for name, check in checks.items():
        try:
            check()
            services[name] = ServiceStatus(status="ok")
        except Exception as exc:  # noqa: BLE001 - any failure means the service is down
            services[name] = ServiceStatus(status="error", detail=type(exc).__name__)
    overall: Literal["ok", "degraded"] = (
        "ok" if all(s.status == "ok" for s in services.values()) else "degraded"
    )
    return HealthResponse(status=overall, services=services)


class MissingExtensionError(RuntimeError):
    pass


@lru_cache
def _engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def _check_database(settings: Settings) -> None:
    with _engine(settings.database_url).connect() as conn:
        conn.execute(text("SELECT 1"))


def _check_pgvector(settings: Settings) -> None:
    with _engine(settings.database_url).connect() as conn:
        found = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
    if found is None:
        raise MissingExtensionError("vector")


def _check_redis(settings: Settings) -> None:
    client = redis.Redis.from_url(settings.redis_url, socket_timeout=3, socket_connect_timeout=3)
    try:
        client.ping()
    finally:
        client.close()


def _check_storage(settings: Settings) -> None:
    make_s3_client(settings).head_bucket(Bucket=settings.s3_bucket)


def get_checks() -> dict[str, ServiceCheck]:
    settings = get_settings()
    return {
        "database": lambda: _check_database(settings),
        "pgvector": lambda: _check_pgvector(settings),
        "redis": lambda: _check_redis(settings),
        "storage": lambda: _check_storage(settings),
    }
