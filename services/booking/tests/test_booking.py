from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from booking_app import main
from booking_app.auth import Principal, current_user
from booking_app.db import get_session
from booking_app.models import Booking, OutboxEvent, VisitSlot
from booking_app.schemas import SlotWrite, TierQuote

TIER = uuid4()


@pytest.fixture(autouse=True)
def clock_and_quote(monkeypatch):
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 15, 5, tzinfo=UTC))
    quote = TierQuote(
        id=TIER,
        code="FAMILY",
        name="Family",
        min_guests=1,
        max_guests=4,
        amount_minor=14000,
        currency="USD",
        price_version=1,
    )
    monkeypatch.setattr(main, "get_quote", lambda tier_id: quote)
    return quote


@pytest.fixture
def slot(booking_session):
    row = main.create_slot(
        booking_session,
        SlotWrite(
            visit_date=date(2026, 10, 16), start_time=time(9), end_time=time(12), capacity_guests=5
        ),
    )
    return row


def body(slot, **changes):
    return {
        "tier_id": str(TIER),
        "slot_id": str(slot.id),
        "guest_count": 4,
        "expected_price_version": 1,
        **changes,
    }


def reserve(client, slot, key=None, **changes):
    return client.post(
        "/api/v1/bookings",
        json=body(slot, **changes),
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def test_snapshot_ownership_and_cancel(booking_client, booking_session, slot, clock_and_quote):
    result = reserve(booking_client, slot)
    assert result.status_code == 201
    booking = result.json()
    assert booking["amount_minor"] == 14000 and booking["status"] == "PENDING_PAYMENT"
    assert "user_sub" not in booking
    assert booking_client.get("/api/v1/bookings/me").json()[0]["id"] == booking["id"]
    clock_and_quote.amount_minor = 99999
    assert booking_client.get(f"/api/v1/bookings/{booking['id']}").json()["amount_minor"] == 14000
    booking_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="bob", username="bob", role="administrator"
    )
    assert booking_client.get("/api/v1/bookings/me").json() == []
    assert booking_client.get(f"/api/v1/bookings/{booking['id']}").status_code == 404
    assert booking_client.post(f"/api/v1/bookings/{booking['id']}/cancel").status_code == 404
    booking_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="alice", username="alice", role="visitor"
    )
    for _ in range(2):
        assert (
            booking_client.post(f"/api/v1/bookings/{booking['id']}/cancel").json()["status"]
            == "CANCELLED"
        )
    booking_session.expire_all()
    assert booking_session.get(VisitSlot, slot.id).held_guests == 0
    assert booking_session.scalar(select(func.count()).select_from(OutboxEvent)) == 2


def test_idempotency_and_changed_body(booking_client, booking_session, slot, monkeypatch):
    key = uuid4()
    first = reserve(booking_client, slot, key)
    monkeypatch.setattr(main, "get_quote", lambda _: (_ for _ in ()).throw(HTTPException(503)))
    replay = reserve(booking_client, slot, key)
    assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    assert reserve(booking_client, slot, key, guest_count=3).status_code == 409
    booking_session.expire_all()
    assert booking_session.get(VisitSlot, slot.id).held_guests == 4
    assert booking_session.scalar(select(func.count()).select_from(Booking)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"guest_count": 0},
        {"guest_count": 6},
        {"guest_count": 1.5},
        {"guest_count": True},
        {"guest_count": "2"},
        {"guest_count": 5},
        {"user_sub": "bob"},
        {"amount_minor": 1},
        {"status": "CONFIRMED"},
    ],
)
def test_invalid_or_untrusted_body(booking_client, slot, changes):
    assert reserve(booking_client, slot, **changes).status_code == 422


def test_capacity_and_stale_price(booking_client, slot):
    assert reserve(booking_client, slot, expected_price_version=99).status_code == 409
    assert reserve(booking_client, slot).status_code == 201
    assert reserve(booking_client, slot).status_code == 409
    assert reserve(booking_client, slot, guest_count=1).status_code == 201
    assert (
        booking_client.get("/api/v1/visit-slots?date=2026-10-16").json()[0]["remaining_guests"] == 0
    )


def test_expiry_releases_once(booking_client, booking_session, slot, monkeypatch):
    booking = reserve(booking_client, slot).json()
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 15, 5, 31, tzinfo=UTC))
    for _ in range(2):
        assert (
            booking_client.get("/api/v1/visit-slots?date=2026-10-16").json()[0]["remaining_guests"]
            == 5
        )
    assert booking_client.get(f"/api/v1/bookings/{booking['id']}").json()["status"] == "EXPIRED"
    assert booking_session.scalar(select(func.count()).select_from(OutboxEvent)) == 2


def test_outbox_failure_rolls_back_capacity(booking_client, booking_session, slot, monkeypatch):
    def fail(*args):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(main, "event", fail)
    with pytest.raises(RuntimeError):
        reserve(booking_client, slot)
    booking_session.expire_all()
    assert booking_session.get(VisitSlot, slot.id).held_guests == 0
    assert booking_session.scalar(select(func.count()).select_from(Booking)) == 0


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/booking-policy",
        "/api/v1/bookings/me",
        "/api/v1/visit-slots?date=2026-10-16",
        f"/api/v1/bookings/{uuid4()}",
    ],
)
def test_unauthenticated_reads_rejected(booking_client, path):
    booking_client.app.dependency_overrides.pop(current_user)
    assert booking_client.get(path).status_code == 401


def test_auth_on_writes(booking_client, slot):
    data = {
        "visit_date": "2026-10-17",
        "start_time": "09:00",
        "end_time": "12:00",
        "capacity_guests": 10,
    }
    assert booking_client.post("/api/v1/admin/visit-slots", json=data).status_code == 403
    booking_client.app.dependency_overrides.pop(current_user)
    assert reserve(booking_client, slot).status_code == 401
    assert booking_client.post(f"/api/v1/bookings/{uuid4()}/cancel").status_code == 401
    assert booking_client.post("/api/v1/admin/visit-slots", json=data).status_code == 401


def test_admin_slots_overlap_and_date_validation(booking_client, slot):
    booking_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="admin", username="admin", role="administrator"
    )
    data = {
        "visit_date": "2026-10-16",
        "start_time": "12:00",
        "end_time": "15:00",
        "capacity_guests": 10,
    }
    assert booking_client.post("/api/v1/admin/visit-slots", json=data).status_code == 201
    assert booking_client.post("/api/v1/admin/visit-slots", json=data).status_code == 409
    for change in [
        {"start_time": "11:00"},
        {"start_time": "12:00", "end_time": "11:00"},
        {"capacity_guests": 0},
        {"start_time": "12:00:01"},
        {"visit_date": "2026-10-14"},
        {"visit_date": "2027-10-15"},
    ]:
        assert booking_client.post(
            "/api/v1/admin/visit-slots", json={**data, **change}
        ).status_code in {409, 422}
    assert booking_client.get("/api/v1/visit-slots?date=2026-10-14").status_code == 422
    assert booking_client.get("/api/v1/bookings/me?limit=101").status_code == 422


def test_timezone_boundary(booking_client, monkeypatch):
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 15, 19, tzinfo=UTC))
    assert booking_client.get("/api/v1/booking-policy").json()["today"] == "2026-10-16"
    assert booking_client.get("/api/v1/visit-slots?date=2026-10-15").status_code == 422


def test_started_slot_rejected(booking_client, slot, monkeypatch):
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 16, 4, tzinfo=UTC))
    assert reserve(booking_client, slot).status_code == 409
    assert booking_client.get("/api/v1/visit-slots?date=2026-10-16").json() == []


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_reservations(booking_engine, monkeypatch, same_key):
    # Independently committed disposable rows in the separate test schema, real PostgreSQL locks.
    owner = "concurrency-" + uuid4().hex
    with Session(booking_engine, expire_on_commit=False) as session, session.begin():
        slot = main.create_slot(
            session,
            SlotWrite(
                visit_date=date(2026, 10, 18),
                start_time=time(9),
                end_time=time(12),
                capacity_guests=4,
            ),
        )
        slot_id = slot.id
    gate = Barrier(2)
    key = uuid4()

    def run(index):
        app = main.create_app()

        def db():
            with Session(booking_engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_session] = db
        app.dependency_overrides[current_user] = lambda: Principal(
            user_id=owner, username=owner, role="visitor"
        )
        with TestClient(app) as client:
            gate.wait(timeout=10)
            return reserve(client, slot, key if same_key else uuid4()).status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = list(executor.map(run, range(2)))
        assert sorted(codes) == ([200, 201] if same_key else [201, 409])
        with Session(booking_engine) as session:
            assert session.get(VisitSlot, slot_id).held_guests == 4
            assert (
                session.scalar(
                    select(func.count()).select_from(Booking).where(Booking.slot_id == slot_id)
                )
                == 1
            )
    finally:
        with Session(booking_engine) as session, session.begin():
            ids = select(Booking.id).where(Booking.slot_id == slot_id)
            session.execute(delete(OutboxEvent).where(OutboxEvent.booking_id.in_(ids)))
            session.execute(delete(Booking).where(Booking.slot_id == slot_id))
            session.execute(delete(VisitSlot).where(VisitSlot.id == slot_id))


def test_booking_role_cannot_read_catalog(booking_session):
    # Verify schema isolation, not merely a naming convention.
    from sqlalchemy.exc import ProgrammingError

    with pytest.raises(ProgrammingError), booking_session.begin_nested():
        booking_session.execute(text("SELECT id FROM catalog.attractions LIMIT 1"))
