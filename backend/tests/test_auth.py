import pytest
from conftest import Api
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import User, require_role
from app.config import Settings, get_settings


def test_me_returns_the_dev_user_and_roles(api: Api) -> None:
    response = api.as_("tecnico").get("/api/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "dev:tecnico"
    assert [r["id"] for r in body["roles"]] == ["redator", "tecnico"]
    assert body["roles"][1]["label"] == "Técnico responsável"


@pytest.mark.parametrize("login", [None, "", "intruso"])
def test_missing_or_unknown_user_is_401(api: Api, login: str | None) -> None:
    assert api.as_(login).get("/api/me").status_code == 401


def test_dev_users_lists_the_four_roles(api: Api) -> None:
    logins = [u["login"] for u in api.as_(None).get("/api/dev/users").json()]
    assert logins == ["redator", "tecnico", "curador", "admin"]


def test_without_dev_auth_there_are_no_dev_users(app: FastAPI) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(dev_auth=False)
    client = TestClient(app, headers={"X-Dev-User": "admin"})

    assert client.get("/api/dev/users").status_code == 404
    assert client.get("/api/me").status_code == 401


@pytest.fixture
def guarded() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: Settings(dev_auth=True)

    @app.post("/confirm")
    def confirm(user: User = Depends(require_role("tecnico"))) -> dict[str, str]:  # noqa: B008
        return {"by": user.id}

    return TestClient(app)


@pytest.mark.parametrize(
    ("login", "expected"), [("tecnico", 200), ("redator", 403), ("curador", 403), ("admin", 403)]
)
def test_require_role_lets_only_the_right_roles_through(
    guarded: TestClient, login: str, expected: int
) -> None:
    response = guarded.post("/confirm", headers={"X-Dev-User": login})

    assert response.status_code == expected
    if expected == 403:
        assert "Técnico responsável" in response.json()["detail"]


def test_require_role_rejects_unknown_roles() -> None:
    with pytest.raises(ValueError, match="unknown roles"):
        require_role("chefe")
