"""Development simulator: no card data, provider callbacks or real charges."""

import json
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from payment_app.auth import CurrentUser
from payment_app.config import get_settings
from payment_app.db import get_session
from payment_app.models import Checkout

DatabaseSession = Annotated[Session, Depends(get_session)]


class CheckoutWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_id: UUID


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["success", "failure"]


def view(row):
    return {
        "id": row.id,
        "booking_id": row.booking_id,
        "booking_reference": row.booking_reference,
        "amount_minor": row.amount_minor,
        "currency": row.currency,
        "status": row.status,
        "outcome": row.outcome,
        "mode": "MOCK",
    }


def gate():
    if not get_settings().mock_payments_enabled:
        raise HTTPException(404, "Mock payment simulation is disabled")


def call_booking(path, authorization, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = Request(
        get_settings().booking_url.rstrip("/") + "/api/v1/bookings/" + path,
        data=data,
        headers={"Authorization": authorization, "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=6) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise ValueError("Oversize Booking response")
        return json.loads(raw)
    except HTTPError as exc:
        if exc.code in {401, 403, 404, 409, 422}:
            raise HTTPException(
                exc.code, "Booking rejected this request. Refresh your reservation."
            ) from exc
        raise HTTPException(
            503, "Booking outcome is unknown; retry the same mock checkout."
        ) from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise HTTPException(
            503, "Booking outcome is unknown; retry the same mock checkout."
        ) from exc


def create_app():
    app = FastAPI(title="Wonderland MOCK Payment", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def no_store(request, call_next):
        result = await call_next(request)
        result.headers["Cache-Control"] = "no-store"
        return result

    @app.get("/health/live")
    def live():
        return {
            "status": "ok",
            "service": "payment",
            "mode": "MOCK",
            "mock_enabled": get_settings().mock_payments_enabled,
        }

    @app.get("/health/ready")
    def ready(session: DatabaseSession):
        try:
            session.execute(text("SELECT id FROM payment.mock_checkouts LIMIT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(503, "Payment storage is not ready") from exc
        return {"status": "ready", "service": "payment", "mode": "MOCK"}

    @app.post("/api/v1/payments/checkouts")
    def create(
        body: CheckoutWrite,
        user: CurrentUser,
        session: DatabaseSession,
        authorization: Annotated[str, Header()],
    ):
        gate()
        booking = call_booking(str(body.booking_id), authorization)
        with session.begin():
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": f"checkout:{body.booking_id}"},
            )
            existing = session.scalar(
                select(Checkout).where(Checkout.booking_id == body.booking_id)
            )
            if existing:
                if existing.user_sub != user.user_id:
                    raise HTTPException(404, "Checkout not found")
                return view(existing)
            if booking["status"] != "PENDING_PAYMENT":
                raise HTTPException(409, "Choose an active unpaid reservation.")
            row = Checkout(
                booking_id=body.booking_id,
                user_sub=user.user_id,
                amount_minor=booking["amount_minor"],
                currency=booking["currency"],
                booking_reference=booking["reference"],
            )
            session.add(row)
            session.flush()
            return view(row)

    @app.get("/api/v1/payments/checkouts/{checkout_id}")
    def detail(checkout_id: UUID, user: CurrentUser, session: DatabaseSession):
        gate()
        row = session.scalar(
            select(Checkout).where(Checkout.id == checkout_id, Checkout.user_sub == user.user_id)
        )
        if row is None:
            raise HTTPException(404, "Checkout not found")
        return view(row)

    @app.post("/api/v1/payments/checkouts/{checkout_id}/complete")
    def complete(
        checkout_id: UUID,
        body: Decision,
        user: CurrentUser,
        session: DatabaseSession,
        authorization: Annotated[str, Header()],
    ):
        gate()
        with session.begin():
            row = session.scalar(
                select(Checkout)
                .where(Checkout.id == checkout_id, Checkout.user_sub == user.user_id)
                .with_for_update()
            )
            if row is None:
                raise HTTPException(404, "Checkout not found")
            if row.outcome is not None and row.outcome != body.outcome:
                raise HTTPException(409, "Retry the existing mock outcome; it cannot be changed.")
            if row.status in {"SUCCEEDED", "FAILED", "REJECTED"}:
                return view(row)
            row.outcome = body.outcome
            row.status = "DECIDED"
            booking_id = row.booking_id
        try:
            booking = call_booking(
                f"{booking_id}/mock-payment",
                authorization,
                {"checkout_id": str(checkout_id), "outcome": body.outcome},
            )
        except HTTPException as exc:
            if exc.status_code in {404, 409, 422}:
                with session.begin():
                    row = session.get(Checkout, checkout_id, with_for_update=True)
                    row.status = "REJECTED"
                    result = view(row)
                return result
            raise
        expected = "CONFIRMED" if body.outcome == "success" else "PAYMENT_FAILED"
        if booking.get("status") != expected:
            raise HTTPException(503, "Unexpected booking result; retry the same checkout.")
        with session.begin():
            row = session.get(Checkout, checkout_id, with_for_update=True)
            row.status = "SUCCEEDED" if body.outcome == "success" else "FAILED"
            return view(row)

    return app


app = create_app()
