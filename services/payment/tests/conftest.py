import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command

URL = os.environ.get(
    "PAYMENT_TEST_DATABASE_URL",
    "postgresql+psycopg://payment_test:payment_test_only@localhost:55432/wonderland_test",
)
if not (make_url(URL).database or "").endswith("_test"):
    raise RuntimeError("Payment tests require an isolated _test database")
os.environ["PAYMENT_DATABASE_URL"] = URL

from payment_app import main  # noqa: E402
from payment_app.auth import Principal, current_user  # noqa: E402
from payment_app.config import get_settings  # noqa: E402
from payment_app.db import get_engine, get_session  # noqa: E402


@pytest.fixture(scope="session")
def payment_engine():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    engine = get_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def payment_client(payment_engine, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_payments_enabled", True)
    with payment_engine.connect() as connection:
        outer = connection.begin()
        app = main.create_app()

        def override():
            with Session(
                bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            ) as session:
                yield session

        app.dependency_overrides[get_session] = override
        app.dependency_overrides[current_user] = lambda: Principal(
            user_id="alice", username="alice", role="visitor"
        )
        with TestClient(app) as client:
            yield client
        outer.rollback()
