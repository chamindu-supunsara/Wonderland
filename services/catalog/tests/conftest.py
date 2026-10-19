import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command

# Force tests onto an explicit separate database, regardless of the development .env.
TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://catalog_test:catalog_test_only@localhost:55432/wonderland_test",
)
if not (make_url(TEST_URL).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must target a database whose name ends with _test")
os.environ["DATABASE_URL"] = TEST_URL

from app.db import get_engine, get_session  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    migration_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(migration_config, "head")
    database_engine = get_engine()
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def session(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as database_session:
            yield database_session
        transaction.rollback()


@pytest.fixture
def client(session):
    app = create_app()

    def use_test_session():
        # Each HTTP request gets its own unit of work, joined to the rollback-only test connection.
        with Session(
            bind=session.connection(),
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as request_session:
            yield request_session

    app.dependency_overrides[get_session] = use_test_session
    with TestClient(app) as test_client:
        yield test_client
