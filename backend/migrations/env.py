from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401 - registers every table
from app.config import get_settings
from app.db import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.attributes.get("database_url") or get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return str(url)


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
