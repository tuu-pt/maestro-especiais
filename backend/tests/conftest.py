"""Database fixtures: a migrated maestro_test database and one rolled-back transaction per test."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from support import test_database_url

BACKEND = Path(__file__).resolve().parents[1]


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
