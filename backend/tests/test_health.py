from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.health import ServiceCheck, get_checks
from app.main import create_app

ClientFactory = Callable[[dict[str, ServiceCheck]], TestClient]


def _ok() -> None:
    return None


def _down() -> None:
    raise ConnectionRefusedError("postgresql://user:secret@db:5432/maestro")


@pytest.fixture
def client_with() -> Iterator[ClientFactory]:
    app = create_app()

    def make(checks: dict[str, ServiceCheck]) -> TestClient:
        app.dependency_overrides[get_checks] = lambda: checks
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def test_all_services_ok_returns_200(client_with: ClientFactory) -> None:
    client = client_with({"database": _ok, "pgvector": _ok, "redis": _ok, "storage": _ok})

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["services"]) == {"database", "pgvector", "redis", "storage"}
    assert all(s["status"] == "ok" for s in body["services"].values())


def test_one_service_down_returns_503_with_detail(client_with: ClientFactory) -> None:
    client = client_with({"database": _down, "redis": _ok})

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["database"] == {
        "status": "error",
        "detail": "ConnectionRefusedError",
    }
    assert body["services"]["redis"]["status"] == "ok"


def test_error_detail_never_leaks_exception_message(client_with: ClientFactory) -> None:
    client = client_with({"database": _down})

    response = client.get("/api/health")

    assert "secret" not in response.text
    assert "postgresql://" not in response.text
