import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from analytics_app.worker import apply_booking
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker
from wonderland_events.transport import Event, consume_one

from alembic import command


@pytest.fixture
def analytics_factory(monkeypatch):
    url = os.environ.get(
        "ANALYTICS_TEST_DATABASE_URL",
        "postgresql+psycopg://analytics_test:analytics_test_only@127.0.0.1:55432/wonderland_test",
    )
    assert make_url(url).database.endswith("_test")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(
        Config(str(Path(__file__).resolve().parents[1] / "services/analytics/alembic.ini")), "head"
    )
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
        yield factory
        transaction.rollback()
    engine.dispose()


def test_analytics_retains_latest_snapshot_and_deduplicates(analytics_factory):
    booking_id = uuid4()
    messages = [
        Event(
            event_id=uuid4(),
            source="booking",
            event_type=kind,
            aggregate_id=booking_id,
            aggregate_version=version,
            occurred_at=datetime.now(UTC),
            data={"id": str(booking_id), "status": status, "guest_count": 4, "amount_minor": 14000},
        )
        for version, kind, status in [
            (2, "BookingCancelled", "CANCELLED"),
            (1, "BookingPaymentRequested", "PENDING_PAYMENT"),
        ]
    ]

    class Queue:
        deleted = 0
        body = ""

        def receive_message(self, **kw):
            return {"Messages": [{"Body": self.body, "ReceiptHandle": "receipt"}]}

        def delete_message(self, **kw):
            self.deleted += 1

    queue = Queue()
    for item in [messages[0], messages[1], messages[0]]:
        queue.body = item.model_dump_json()
        consume_one(analytics_factory, "analytics", "test", "url", queue, apply_booking, wait=0)
    assert queue.deleted == 3
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.event_inbox")) == 2
        assert (
            session.scalar(text("SELECT payload->>'status' FROM analytics.booking_projection"))
            == "CANCELLED"
        )
        with pytest.raises(ProgrammingError):
            session.execute(text("SELECT * FROM booking.bookings"))


def confirmation(booking_id=None, **changes):
    booking_id = booking_id or uuid4()
    data = {
        "id": str(booking_id),
        "status": "CONFIRMED",
        "guest_count": 4,
        "amount_minor": 14000,
        "tier_code": "FAMILY",
        "currency": "USD",
        "payment_mode": "MOCK",
    }
    data.update(changes)
    return Event(
        event_id=uuid4(),
        source="booking",
        event_type="MockBookingConfirmed",
        aggregate_id=booking_id,
        aggregate_version=2,
        occurred_at=datetime(2026, 10, 18, 19, 0, tzinfo=UTC),
        data=data,
    )


def test_mock_purchase_is_idempotent_and_uses_confirmation_date_in_colombo(analytics_factory):
    event = confirmation()
    with analytics_factory.begin() as session:
        apply_booking(session, event)
        apply_booking(session, event)
        row = session.execute(
            text(
                "SELECT purchase_date,purchases,guest_tickets,simulated_revenue_minor,mode "
                "FROM reporting.mock_daily_purchases"
            )
        ).one()
        assert str(row.purchase_date) == "2026-10-19"
        assert tuple(row[1:]) == (1, 4, 14000, "MOCK")
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_purchases")) == 1


def test_mock_purchase_conflicting_confirmation_rolls_back(analytics_factory):
    event = confirmation()
    with analytics_factory.begin() as session:
        apply_booking(session, event)
    altered = event.model_copy(update={"data": {**event.data, "amount_minor": 1}})
    with pytest.raises(ValueError, match="Conflicting purchase"):
        with analytics_factory.begin() as session:
            apply_booking(session, altered)
    with analytics_factory() as session:
        assert session.scalar(text("SELECT amount_minor FROM analytics.mock_purchases")) == 14000


@pytest.mark.parametrize(
    "change", [{"payment_mode": "NONE"}, {"currency": "EUR"}, {"tier_code": "PRIVATE"}]
)
def test_purchase_rejects_unlabelled_or_invalid_confirmation(analytics_factory, change):
    with pytest.raises(ValueError):
        with analytics_factory.begin() as session:
            apply_booking(session, confirmation(**change))
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_purchases")) == 0
