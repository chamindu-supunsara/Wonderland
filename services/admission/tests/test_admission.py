from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from admission_app import main, upstream
from admission_app.auth import Principal, current_user
from admission_app.config import get_settings
from admission_app.db import get_session
from admission_app.models import Admission, OutboxEvent, RideUse, Ticket
from admission_app.schemas import TicketSnapshot
from admission_app.upstream import ActiveAttraction
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

TIME = "2026-10-16T09:00:00+05:30"


@pytest.fixture
def snapshot(monkeypatch):
    ticket = TicketSnapshot(
        id=uuid4(),
        reference="MOCK-" + uuid4().hex.upper(),
        booking_id=uuid4(),
        booking_reference="WL-DEMO",
        user_sub="alice",
        guest_number=1,
        tier_code="FAMILY",
        tier_name="Family",
        starts_at=TIME,
        ends_at="2026-10-16T12:00:00+05:30",
        status="CONFIRMED",
        payment_mode="MOCK",
    )
    monkeypatch.setattr(main, "get_ticket", lambda reference, authorization: ticket)
    monkeypatch.setattr(
        main,
        "get_attraction",
        lambda ident: ActiveAttraction(id=ident, name="River Ride", category="Family"),
    )
    return ticket


def check_in(client, snapshot, **changes):
    return client.post(
        "/api/v1/admissions/staff/check-ins",
        json={"ticket_reference": snapshot.reference, "simulation_time": TIME, **changes},
        headers={"Authorization": "Bearer test"},
    )


def ride(client, snapshot, key=None, **changes):
    return client.post(
        "/api/v1/admissions/staff/ride-uses",
        json={
            "ticket_reference": snapshot.reference,
            "simulation_time": TIME,
            "attraction_id": str(uuid4()),
            **changes,
        },
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_guest_entry_replay_and_projection(admission_client, admission_session, snapshot):
    for index in range(2):
        response = check_in(admission_client, snapshot)
        assert response.status_code == (201 if index == 0 else 200), response.text
        assert response.json()["already_checked_in"] == bool(index)
    assert count(admission_session, Admission) == 1
    assert count(admission_session, OutboxEvent) == 1
    event = admission_session.scalar(select(OutboxEvent))
    assert event.payload["mode"] == "MOCK" and event.event_type == "MockGuestCheckedIn"
    assert "recorded_at" in event.payload and "occurred_at" in event.payload
    lookup = admission_client.get(
        "/api/v1/admissions/staff/tickets/" + snapshot.reference,
        headers={"Authorization": "Bearer test"},
    ).json()
    assert lookup["check_in"]["id"] == response.json()["id"]
    assert "user_sub" not in lookup["ticket"]


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-16T08:59:00+05:30",
        "2026-10-16T12:00:00+05:30",
        "2026-10-17T09:00:00+05:30",
        "2026-10-16T09:00:00",
    ],
)
def test_time_window_and_timezone(timestamp, admission_client, admission_session, snapshot):
    assert check_in(admission_client, snapshot, simulation_time=timestamp).status_code == 422
    assert count(admission_session, Admission) == 0


def test_ride_requires_checkin(admission_client, snapshot):
    assert ride(admission_client, snapshot).status_code == 409


def test_ride_retry_new_use_and_owner_history(admission_client, admission_session, snapshot):
    visit = check_in(admission_client, snapshot).json()
    key, attraction = uuid4(), str(uuid4())
    first = ride(admission_client, snapshot, key, attraction_id=attraction)
    assert first.status_code == 201, first.text
    assert ride(admission_client, snapshot, key, attraction_id=attraction).json() == first.json()
    assert (
        ride(
            admission_client,
            snapshot,
            key,
            attraction_id=attraction,
            simulation_time="2026-10-16T09:05:00+05:30",
        ).status_code
        == 409
    )
    assert ride(admission_client, snapshot, attraction_id=attraction).status_code == 201
    assert count(admission_session, RideUse) == 2 and count(admission_session, OutboxEvent) == 3
    assert sorted(admission_session.scalars(select(OutboxEvent.aggregate_version)).all()) == [
        1,
        2,
        3,
    ]
    admission_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="alice", username="alice", role="visitor"
    )
    history = admission_client.get("/api/v1/admissions/visits/me").json()
    assert history[0]["ride_count"] == 2
    assert len(admission_client.get(f"/api/v1/admissions/visits/{visit['id']}/rides").json()) == 2
    admission_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="other", username="other", role="administrator"
    )
    assert admission_client.get("/api/v1/admissions/visits/me").json() == []
    assert admission_client.get(f"/api/v1/admissions/visits/{visit['id']}/rides").status_code == 404


def test_ride_before_checkin_and_slot_end(admission_client, snapshot):
    assert (
        check_in(
            admission_client, snapshot, simulation_time="2026-10-16T10:00:00+05:30"
        ).status_code
        == 201
    )
    assert ride(admission_client, snapshot).status_code == 422
    assert (
        ride(admission_client, snapshot, simulation_time="2026-10-16T12:00:00+05:30").status_code
        == 422
    )


def test_atomic_outbox_failure(admission_client, admission_session, snapshot, monkeypatch):
    def fail(*args):
        raise RuntimeError("injected outbox failure")

    monkeypatch.setattr(main, "emit", fail)
    with pytest.raises(RuntimeError, match="injected"):
        check_in(admission_client, snapshot)
    assert (
        count(admission_session, Admission)
        == count(admission_session, Ticket)
        == count(admission_session, OutboxEvent)
        == 0
    )


@pytest.mark.parametrize("code", [404, 409, 503])
def test_invalid_ticket_upstream_fails_closed(
    code, admission_client, admission_session, snapshot, monkeypatch
):
    def fail(*args):
        raise HTTPException(code)

    monkeypatch.setattr(main, "get_ticket", fail)
    assert check_in(admission_client, snapshot).status_code == code
    assert count(admission_session, Admission) == 0


def test_retired_attraction_rejects_new_use_but_replay_works(
    admission_client, snapshot, monkeypatch
):
    check_in(admission_client, snapshot)
    key, attraction = uuid4(), str(uuid4())
    row = ride(admission_client, snapshot, key, attraction_id=attraction).json()

    def retired(*args):
        raise HTTPException(404)

    monkeypatch.setattr(main, "get_attraction", retired)
    assert ride(admission_client, snapshot, key, attraction_id=attraction).json() == row
    assert ride(admission_client, snapshot, attraction_id=attraction).status_code == 404


def test_role_gate_and_authentication(admission_client, snapshot, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_admission_enabled", False)
    assert check_in(admission_client, snapshot).status_code == 404
    monkeypatch.setattr(get_settings(), "mock_admission_enabled", True)
    admission_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="alice", username="alice", role="visitor"
    )
    assert check_in(admission_client, snapshot).status_code == 403
    assert ride(admission_client, snapshot).status_code == 403
    assert (
        admission_client.get(
            "/api/v1/admissions/staff/tickets/" + snapshot.reference,
            headers={"Authorization": "Bearer test"},
        ).status_code
        == 403
    )
    admission_client.app.dependency_overrides.clear()
    assert admission_client.get("/api/v1/admissions/visits/me").status_code == 401


@pytest.mark.parametrize("schema", ["booking", "catalog", "payment"])
def test_database_isolation(admission_engine, schema):
    with admission_engine.connect() as connection:
        with pytest.raises(DBAPIError, match="permission denied"):
            connection.execute(
                text(
                    f"SELECT * FROM {schema}."
                    + {
                        "booking": "bookings",
                        "catalog": "attractions",
                        "payment": "mock_checkouts",
                    }[schema]
                )
            )


@pytest.mark.parametrize("changes", [{"status": "PENDING_PAYMENT"}, {"payment_mode": "NONE"}])
def test_only_confirmed_mock_snapshots(changes, snapshot, monkeypatch):
    raw = {**snapshot.model_dump(mode="json"), **changes}
    with pytest.raises(ValidationError):
        TicketSnapshot.model_validate(raw)
    monkeypatch.setattr(upstream, "read_json", lambda *args: raw)
    with pytest.raises(HTTPException) as error:
        upstream.get_ticket(snapshot.reference, "Bearer test")
    assert error.value.status_code == 503


def test_concurrent_gate_and_ride_retries(admission_engine, snapshot, monkeypatch):
    monkeypatch.setattr(get_settings(), "mock_admission_enabled", True)
    app = main.create_app()
    app.dependency_overrides[current_user] = lambda: Principal(
        user_id="parallel", username="parallel", role="administrator"
    )

    def sessions():
        with Session(admission_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    barrier = Barrier(4)

    def enter(_):
        with TestClient(app) as client:
            barrier.wait()
            return check_in(client, snapshot).status_code

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(enter, range(4)))
        assert sorted(statuses) == [200, 200, 200, 201]
        key, attraction = uuid4(), str(uuid4())
        barrier = Barrier(4)

        def use(_):
            with TestClient(app) as client:
                barrier.wait()
                return ride(client, snapshot, key, attraction_id=attraction).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sorted(pool.map(use, range(4))) == [200, 200, 200, 201]
        with Session(admission_engine) as session:
            entry = session.scalar(select(Admission).where(Admission.ticket_id == snapshot.id))
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(RideUse)
                    .where(RideUse.admission_id == entry.id)
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(OutboxEvent.aggregate_id == entry.id)
                )
                == 2
            )
    finally:
        with Session(admission_engine) as session, session.begin():
            ids = select(Admission.id).where(Admission.ticket_id == snapshot.id)
            session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_id.in_(ids)))
            session.execute(delete(RideUse).where(RideUse.admission_id.in_(ids)))
            session.execute(delete(Admission).where(Admission.ticket_id == snapshot.id))
            session.execute(delete(Ticket).where(Ticket.id == snapshot.id))


def test_ride_transaction_rolls_back_with_outbox(
    admission_client, admission_session, snapshot, monkeypatch
):
    check_in(admission_client, snapshot)

    def fail(*args):
        raise RuntimeError("injected ride outbox failure")

    monkeypatch.setattr(main, "emit", fail)
    with pytest.raises(RuntimeError, match="injected"):
        ride(admission_client, snapshot)
    admission_session.expire_all()
    assert count(admission_session, RideUse) == 0
    assert count(admission_session, OutboxEvent) == 1
    assert admission_session.scalar(select(Admission)).event_version == 1


def test_changed_projection_rejected(admission_client, snapshot, monkeypatch):
    check_in(admission_client, snapshot)
    monkeypatch.setattr(
        main, "get_ticket", lambda *args: snapshot.model_copy(update={"user_sub": "mallory"})
    )
    assert check_in(admission_client, snapshot).status_code == 409
