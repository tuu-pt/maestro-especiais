"""Database fixtures: a migrated maestro_test database and one rolled-back transaction per test."""

import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from support import test_database_url

from app.config import Settings, get_settings
from app.db import get_session
from app.ingest.pipeline import run_ingestion
from app.jobs import get_publisher, get_queue
from app.main import create_app
from app.storage import ObjectStore, get_store
from app.validation.jobs import get_validation_queue

BACKEND = Path(__file__).resolve().parents[1]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--annex-c-report", default=None,
                     help="write the Annex C report of Phase 5 to this path")  # fmt: skip


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    url = test_database_url()
    try:
        _ensure_database(url)
    except OperationalError:
        pytest.fail("Postgres de teste indisponível: corra `make up` antes de `make test`.")
    engine = create_engine(url)
    with engine.begin() as conn:  # start from an empty schema every session
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine.dispose()
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    eng = create_engine(database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    conn = engine.connect()
    outer = conn.begin()
    yield conn
    outer.rollback()
    conn.close()


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    """Session whose commits become savepoints: everything is rolled back after the test."""
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()


@pytest.fixture
def settings() -> Settings:
    return Settings(dev_auth=True)


class RecordingQueue:
    """Stands in for RQ: remembers what was enqueued (or runs it inline when told to)."""

    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []
        self.run: Callable[[uuid.UUID], None] | None = None
        self.available = True

    def enqueue(self, file_id: uuid.UUID) -> str | None:
        if not self.available:
            return None
        self.enqueued.append(file_id)
        if self.run:
            self.run(file_id)
        return f"job-{len(self.enqueued)}"


class Published(list[tuple[uuid.UUID, dict[str, Any]]]):
    def __call__(self, project_id: uuid.UUID, event: dict[str, Any]) -> None:
        self.append((project_id, event))

    def statuses(self) -> list[str]:
        return [event["status"] for _, event in self]


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
def validation_queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
def published() -> Published:
    return Published()


@pytest.fixture
def store() -> Iterator[ObjectStore]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="maestro-test")
        yield ObjectStore(client, "maestro-test")


@pytest.fixture
def app(
    db: Session,
    settings: Settings,
    queue: RecordingQueue,
    published: Published,
    store: ObjectStore,
    validation_queue: RecordingQueue,
) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_session] = lambda: db
    application.dependency_overrides[get_queue] = lambda: queue
    application.dependency_overrides[get_publisher] = lambda: published
    application.dependency_overrides[get_store] = lambda: store
    application.dependency_overrides[get_validation_queue] = lambda: validation_queue
    return application


@pytest.fixture
def inline_ingestion(
    db: Session, store: ObjectStore, queue: RecordingQueue, published: Published
) -> None:
    """Uploads are read at once, in the test transaction, as the worker would."""
    queue.run = lambda file_id: run_ingestion(db, store, published, file_id)


class Api:
    """Test client that calls the API as one of the development users."""

    def __init__(self, app: FastAPI) -> None:
        self.client = TestClient(app)

    def as_(self, login: str | None) -> TestClient:
        self.client.headers.pop("X-Dev-User", None)
        if login:
            self.client.headers["X-Dev-User"] = login
        return self.client


@pytest.fixture
def api(app: FastAPI) -> Api:
    return Api(app)
