from uuid import uuid4

import pytest
from fastapi import HTTPException
from payment_app import main
from payment_app.auth import Principal, current_user
from payment_app.config import get_settings
from sqlalchemy import text


def checkout(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "call_booking",
        lambda *args: {
            "status": "PENDING_PAYMENT",
            "amount_minor": 14000,
            "currency": "USD",
            "reference": "WL-TEST",
        },
    )
    booking = str(uuid4())
    result = client.post(
        "/api/v1/payments/checkouts",
        json={"booking_id": booking},
        headers={"Authorization": "Bearer test"},
    )
    assert result.status_code == 200, result.text
    return booking, result.json()


def complete(client, row, outcome="success"):
    return client.post(
        f"/api/v1/payments/checkouts/{row['id']}/complete",
        json={"outcome": outcome},
        headers={"Authorization": "Bearer test"},
    )


def test_price_snapshot_reuse_and_owner(payment_client, monkeypatch):
    bid, row = checkout(payment_client, monkeypatch)
    repeat = payment_client.post(
        "/api/v1/payments/checkouts",
        json={"booking_id": bid},
        headers={"Authorization": "Bearer test"},
    ).json()
    assert repeat == row and row["amount_minor"] == 14000 and row["mode"] == "MOCK"
    assert "user_sub" not in row
    assert (
        payment_client.post(
            "/api/v1/payments/checkouts",
            json={"booking_id": bid, "amount_minor": 1},
            headers={"Authorization": "Bearer test"},
        ).status_code
        == 422
    )
    payment_client.app.dependency_overrides[current_user] = lambda: Principal(
        user_id="bob", username="bob", role="administrator"
    )
    assert payment_client.get(f"/api/v1/payments/checkouts/{row['id']}").status_code == 404
    assert complete(payment_client, row).status_code == 404


@pytest.mark.parametrize(
    "outcome,status,booking_status",
    [("success", "SUCCEEDED", "CONFIRMED"), ("failure", "FAILED", "PAYMENT_FAILED")],
)
def test_decision_replay(payment_client, monkeypatch, outcome, status, booking_status):
    bid, row = checkout(payment_client, monkeypatch)
    calls = []

    def booking(path, authorization, body):
        calls.append((path, body))
        return {"status": booking_status}

    monkeypatch.setattr(main, "call_booking", booking)
    assert complete(payment_client, row, outcome).json()["status"] == status
    assert complete(payment_client, row, outcome).json()["status"] == status
    assert calls == [(f"{bid}/mock-payment", {"checkout_id": row["id"], "outcome": outcome})]
    assert (
        complete(payment_client, row, "failure" if outcome == "success" else "success").status_code
        == 409
    )


@pytest.mark.parametrize("error", [401, 503])
def test_unknown_outcome_preserved_and_retry(payment_client, monkeypatch, error):
    _, row = checkout(payment_client, monkeypatch)

    def unavailable(*args):
        raise HTTPException(error)

    monkeypatch.setattr(main, "call_booking", unavailable)
    assert complete(payment_client, row).status_code == error
    persisted = payment_client.get(f"/api/v1/payments/checkouts/{row['id']}").json()
    assert persisted["status"] == "DECIDED" and persisted["outcome"] == "success"
    assert complete(payment_client, row, "failure").status_code == 409
    monkeypatch.setattr(main, "call_booking", lambda *args: {"status": "CONFIRMED"})
    assert complete(payment_client, row).json()["status"] == "SUCCEEDED"


def test_expired_rejected_and_disabled(payment_client, monkeypatch):
    _, row = checkout(payment_client, monkeypatch)

    def expired(*args):
        raise HTTPException(409)

    monkeypatch.setattr(main, "call_booking", expired)
    assert complete(payment_client, row).json()["status"] == "REJECTED"
    monkeypatch.setattr(get_settings(), "mock_payments_enabled", False)
    assert complete(payment_client, row).status_code == 404


def test_database_isolation(payment_engine):
    from sqlalchemy.exc import DBAPIError

    with payment_engine.connect() as connection:
        with pytest.raises(DBAPIError, match="permission denied"):
            connection.execute(text("SELECT * FROM booking.bookings"))


def test_no_authentication(payment_client):
    payment_client.app.dependency_overrides.clear()
    assert payment_client.get(f"/api/v1/payments/checkouts/{uuid4()}").status_code == 401
