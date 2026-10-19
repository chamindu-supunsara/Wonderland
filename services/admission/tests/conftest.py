import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command

URL = os.environ.get(
    "ADMISSION_TEST_DATABASE_URL",
    "postgresql+psycopg://admission_test:admission_test_only@localhost:55432/wonderland_test",
)
if not (make_url(URL).database or "").endswith("_test"):
    raise RuntimeError("Admission tests require an isolated _test database")
os.environ["ADMISSION_DATABASE_URL"] = URL

from admission_app.auth import Principal, current_user  # noqa: E402
from admission_app.config import get_settings  # noqa: E402
from admission_app.db import get_engine, get_session  # noqa: E402
from admission_app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def admission_engine():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    engine = get_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def admission_session(admission_engine):
    with admission_engine.connect() as connection:
        outer = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        outer.rollback()


@pytest.fixture
def admission_client(admission_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_admission_enabled", True)
    app = create_app()

    def override():
        with Session(
            bind=admission_session.connection(),
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[current_user] = lambda: Principal(
        user_id="staff", username="staff", role="administrator"
    )
    with TestClient(app) as client:
        yield client
