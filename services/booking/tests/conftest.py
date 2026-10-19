import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command

TEST_URL = os.environ.get(
    "BOOKING_TEST_DATABASE_URL",
    "postgresql+psycopg://booking_test:booking_test_only@localhost:55432/wonderland_test",
)
if not (make_url(TEST_URL).database or "").endswith("_test"):
    raise RuntimeError("BOOKING_TEST_DATABASE_URL must end with _test")
os.environ["BOOKING_DATABASE_URL"] = TEST_URL
os.environ["PRICING_MODE"] = "http"  # Step 04 regression cases mock the HTTP quote explicitly.

from booking_app.auth import Principal, current_user  # noqa: E402
from booking_app.db import get_engine, get_session  # noqa: E402
from booking_app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def booking_engine():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    engine = get_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def booking_session(booking_engine):
    with booking_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def booking_client(booking_session):
    app = create_app()

    def session_override():
        with Session(
            bind=booking_session.connection(),
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = lambda: Principal(
        user_id="alice", username="alice", role="visitor"
    )
    with TestClient(app) as client:
        yield client
