from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from wonderland_events.transport import Event, consume_one

from booking_app.pricing_projection import apply_price, projected_quote


def envelope(version=1, **changes):
    tier_id = changes.pop("aggregate_id", uuid4())
    return Event(
        event_id=uuid4(),
        source="catalog",
        event_type="TicketPricePublished",
        aggregate_id=tier_id,
        aggregate_version=version,
        occurred_at=datetime.now(UTC),
        data={
            "id": str(tier_id),
            "code": "FAMILY",
            "name": "Family",
            "min_guests": 1,
            "max_guests": 4,
            "active": True,
            "amount_minor": 14000,
            "currency": "USD",
            "price_version": version,
        },
        **changes,
    )


@pytest.fixture
def factory(booking_session):
    return sessionmaker(bind=booking_session.connection(), join_transaction_mode="create_savepoint")


class Queue:
    def __init__(self, event):
        self.body = event.model_dump_json()
        self.deleted = 0
        self.fail_delete = False

    def receive_message(self, **kwargs):
        return {"Messages": [{"Body": self.body, "ReceiptHandle": "receipt"}]}

    def delete_message(self, **kwargs):
        if self.fail_delete:
            raise TimeoutError()
        self.deleted += 1


def test_commit_before_ack_and_duplicate_after_delete_failure(factory, booking_session):
    item = envelope()
    queue = Queue(item)
    queue.fail_delete = True
    consume_one(factory, "booking", "test", "url", queue, apply_price, wait=0)
    assert queue.deleted == 0
    assert booking_session.scalar(text("SELECT count(*) FROM booking.event_inbox")) == 1
    queue.fail_delete = False
    consume_one(factory, "booking", "test", "url", queue, apply_price, wait=0)
    assert queue.deleted == 1
    assert booking_session.scalar(text("SELECT count(*) FROM booking.event_inbox")) == 1
    assert projected_quote(booking_session, item.aggregate_id).price_version == 1


def test_processing_failure_rolls_back_inbox_and_does_not_ack(factory, booking_session):
    queue = Queue(envelope())

    def fail(session, item):
        apply_price(session, item)
        raise RuntimeError("consumer failure")

    consume_one(factory, "booking", "test", "url", queue, fail, wait=0)
    assert queue.deleted == 0
    assert booking_session.scalar(text("SELECT count(*) FROM booking.event_inbox")) == 0
    assert booking_session.scalar(text("SELECT count(*) FROM booking.ticket_price_projection")) == 0


def test_out_of_order_price_events_cannot_roll_back_projection(factory, booking_session):
    newest = envelope(3)
    old = envelope(1, aggregate_id=newest.aggregate_id)
    for item in [newest, old]:
        consume_one(factory, "booking", "test", "url", Queue(item), apply_price, wait=0)
    assert projected_quote(booking_session, newest.aggregate_id).price_version == 3


def test_reused_event_id_with_changed_body_is_not_acknowledged(factory, booking_session):
    item = envelope()
    consume_one(factory, "booking", "test", "url", Queue(item), apply_price, wait=0)
    item.data["amount_minor"] = 99999
    changed = Queue(item)
    consume_one(factory, "booking", "test", "url", changed, apply_price, wait=0)
    assert changed.deleted == 0
    assert projected_quote(booking_session, item.aggregate_id).amount_minor == 14000


@pytest.mark.parametrize("bad", ["not json", '{"schema_version":2}', '{"event_id":"not-a-uuid"}'])
def test_poison_message_is_retained(factory, bad):
    queue = Queue(envelope())
    queue.body = bad
    consume_one(factory, "booking", "test", "url", queue, apply_price, wait=0)
    assert queue.deleted == 0


def test_unsupported_source_and_mismatched_version_roll_back(factory, booking_session):
    wrong_source = envelope()
    wrong_source.source = "booking"
    wrong_version = envelope()
    wrong_version.data["price_version"] = 2
    for item in [wrong_source, wrong_version]:
        queue = Queue(item)
        consume_one(factory, "booking", "test", "url", queue, apply_price, wait=0)
        assert queue.deleted == 0
    assert booking_session.scalar(text("SELECT count(*) FROM booking.event_inbox")) == 0


def test_missing_projection_fails_closed(booking_session):
    with pytest.raises(HTTPException) as result:
        projected_quote(booking_session, uuid4())
    assert result.value.status_code == 503


def test_inactive_tier_blocks_booking(booking_session):
    item = envelope()
    item.data["active"] = False
    apply_price(booking_session, item)
    with pytest.raises(HTTPException) as result:
        projected_quote(booking_session, item.aggregate_id)
    assert result.value.status_code == 409


def test_booking_projection_mode_uses_local_quote_without_catalog_http(
    booking_client, booking_session, monkeypatch
):
    from datetime import date, time

    from sqlalchemy import select

    from booking_app import main
    from booking_app.config import get_settings
    from booking_app.models import OutboxEvent
    from booking_app.schemas import SlotWrite

    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 15, 5, tzinfo=UTC))
    monkeypatch.setattr(get_settings(), "pricing_mode", "projection")
    monkeypatch.setattr(main, "get_quote", lambda _: pytest.fail("Unexpected Catalog HTTP lookup"))
    item = envelope()
    apply_price(booking_session, item)
    slot = main.create_slot(
        booking_session,
        SlotWrite(
            visit_date=date(2026, 10, 16), start_time=time(9), end_time=time(12), capacity_guests=4
        ),
    )
    response = booking_client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": str(uuid4())},
        json={
            "tier_id": str(item.aggregate_id),
            "slot_id": str(slot.id),
            "guest_count": 4,
            "expected_price_version": 1,
        },
    )
    assert response.status_code == 201 and response.json()["amount_minor"] == 14000
    saved = booking_session.scalar(select(OutboxEvent))
    assert saved.aggregate_version == 1 and saved.aggregate_id == saved.booking_id
