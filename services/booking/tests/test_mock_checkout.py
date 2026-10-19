from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from booking_app import main
from booking_app.auth import Principal, current_user
from booking_app.config import get_settings
from booking_app.models import Booking, GuestTicket, MockSettlement, OutboxEvent, VisitSlot
from booking_app.schemas import SlotWrite, TierQuote


@pytest.fixture
def mock_reservation(booking_session, booking_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_payments_enabled", True)
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 15, 5, tzinfo=UTC))
    tier = uuid4()
    monkeypatch.setattr(
        main,
        "get_quote",
        lambda _: TierQuote(
            id=tier,
            code="FAMILY",
            name="Family",
            min_guests=1,
            max_guests=4,
            amount_minor=14000,
            currency="USD",
            price_version=1,
        ),
    )
    slot = main.create_slot(
        booking_session,
        SlotWrite(
            visit_date=date(2026, 10, 16), start_time=time(9), end_time=time(12), capacity_guests=5
        ),
    )
    result = booking_client.post(
        "/api/v1/bookings",
        json={
            "tier_id": str(tier),
            "slot_id": str(slot.id),
            "guest_count": 4,
            "expected_price_version": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 201
    return result.json(), slot.id


def decision(client, booking, checkout=None, outcome="success"):
    return client.post(
        f"/api/v1/bookings/{booking['id']}/mock-payment",
        json={"checkout_id": str(checkout or uuid4()), "outcome": outcome},
    )


def test_success_replay_tickets_capacity(
    booking_client, booking_session, mock_reservation, monkeypatch
):
    booking, slot_id = mock_reservation
    key = uuid4()
    for _ in range(2):
        response = decision(booking_client, booking, key)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "CONFIRMED"
    tickets = booking_client.get(f"/api/v1/bookings/{booking['id']}/tickets").json()
    assert len(tickets) == 4 and len({row["reference"] for row in tickets}) == 4
    assert all(row["is_mock"] and row["reference"].startswith("MOCK-") for row in tickets)
    booking_session.expire_all()
    slot = booking_session.get(VisitSlot, slot_id)
    assert (slot.held_guests, slot.confirmed_guests) == (0, 4)
    assert booking_session.scalar(select(func.count()).select_from(MockSettlement)) == 1
    assert booking_session.scalar(select(func.count()).select_from(OutboxEvent)) == 2
    assert decision(booking_client, booking, key, "failure").status_code == 409
    assert decision(booking_client, booking).status_code == 409
    assert booking_client.post(f"/api/v1/bookings/{booking['id']}/cancel").status_code == 409
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 15, 6, tzinfo=UTC))
    assert booking_client.get(f"/api/v1/bookings/{booking['id']}").json()["status"] == "CONFIRMED"


def test_failure_releases_without_tickets(booking_client, booking_session, mock_reservation):
    booking, slot_id = mock_reservation
    key = uuid4()
    assert decision(booking_client, booking, key, "failure").json()["status"] == "PAYMENT_FAILED"
    assert decision(booking_client, booking, key, "failure").status_code == 200
    assert booking_client.get(f"/api/v1/bookings/{booking['id']}/tickets").status_code == 409
    booking_session.expire_all()
    slot = booking_session.get(VisitSlot, slot_id)
    assert (slot.held_guests, slot.confirmed_guests) == (0, 0)
    assert booking_session.scalar(select(func.count()).select_from(GuestTicket)) == 0


@pytest.mark.parametrize("terminal", ["cancelled", "expired"])
def test_late_mock_rejected(terminal, booking_client, mock_reservation, monkeypatch):
    booking, _ = mock_reservation
    if terminal == "cancelled":
        booking_client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    else:
        monkeypatch.setattr(
            main, "now", lambda: datetime(2026, 10, 15, 5, tzinfo=UTC) + timedelta(hours=1)
        )
    assert decision(booking_client, booking).status_code == 409


def test_owner_and_gate(booking_client, mock_reservation, monkeypatch):
    booking, _ = mock_reservation
    monkeypatch.setattr(get_settings(), "mock_payments_enabled", False)
    assert decision(booking_client, booking).status_code == 404
    monkeypatch.setattr(get_settings(), "mock_payments_enabled", True)
    booking_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="bob", username="bob", role="administrator"
    )
    assert decision(booking_client, booking).status_code == 404
    assert booking_client.get(f"/api/v1/bookings/{booking['id']}/tickets").status_code == 404


def test_atomic_outbox_failure(booking_client, booking_session, mock_reservation, monkeypatch):
    booking, slot_id = mock_reservation
    # Force the transaction to fail after capacity, receipt and tickets were changed.
    from booking_app import mock_checkout

    original = mock_checkout.settle

    def fail(*args):
        original(*args)
        raise RuntimeError("injected transaction failure")

    monkeypatch.setattr(mock_checkout, "settle", fail)
    with pytest.raises(RuntimeError, match="injected"):
        decision(booking_client, booking)
    booking_session.expire_all()
    assert booking_session.get(Booking, UUID(booking["id"])).status == "PENDING_PAYMENT"
    assert booking_session.get(VisitSlot, slot_id).held_guests == 4
    assert booking_session.scalar(select(func.count()).select_from(GuestTicket)) == 0
    assert booking_session.scalar(select(func.count()).select_from(MockSettlement)) == 0


def test_staff_ticket_export_requires_administrator(booking_client, mock_reservation, monkeypatch):
    booking, _ = mock_reservation
    assert decision(booking_client, booking).status_code == 200
    reference = booking_client.get(f"/api/v1/bookings/{booking['id']}/tickets").json()[0][
        "reference"
    ]
    path = f"/api/v1/admin/mock-tickets/{reference}"
    assert booking_client.get(path).status_code == 403
    booking_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="staff", username="staff", role="administrator"
    )
    response = booking_client.get(path)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CONFIRMED"
    assert response.json()["payment_mode"] == "MOCK"
    assert response.json()["user_sub"] == "alice"
    assert (
        booking_client.get("/api/v1/admin/mock-tickets/MOCK-" + uuid4().hex.upper()).status_code
        == 404
    )
    monkeypatch.setattr(get_settings(), "mock_payments_enabled", False)
    assert booking_client.get(path).status_code == 404
