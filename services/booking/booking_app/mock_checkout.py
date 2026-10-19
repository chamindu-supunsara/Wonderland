"""Owner-controlled simulation only; no provider payment or financial proof."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text

from booking_app.auth import CurrentUser
from booking_app.config import get_settings
from booking_app.models import Booking, GuestTicket, MockSettlement, VisitSlot


class MockOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkout_id: UUID
    outcome: Literal["success", "failure"]


def settle(session, booking_id, user_id, body, timestamp, emit, expire_slot):
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"mock-checkout:{body.checkout_id}"},
    )
    prior = session.get(MockSettlement, body.checkout_id)
    if prior is not None and prior.booking_id != booking_id:
        raise HTTPException(409, "This checkout belongs to a different booking.")
    owned = session.scalar(
        select(Booking).where(Booking.id == booking_id, Booking.user_sub == user_id)
    )
    if owned is None:
        raise HTTPException(404, "Booking not found")
    slot = session.scalar(select(VisitSlot).where(VisitSlot.id == owned.slot_id).with_for_update())
    expire_slot(session, slot, timestamp)
    booking = session.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    receipt = session.scalar(select(MockSettlement).where(MockSettlement.booking_id == booking.id))
    if receipt:
        if receipt.checkout_id != body.checkout_id or receipt.outcome != body.outcome:
            raise HTTPException(409, "This booking already has a different mock decision.")
        return booking
    if booking.status != "PENDING_PAYMENT" or booking.starts_at <= timestamp:
        raise HTTPException(409, "This reservation can no longer be completed.")
    session.add(
        MockSettlement(checkout_id=body.checkout_id, booking_id=booking.id, outcome=body.outcome)
    )
    slot.held_guests -= booking.guest_count
    booking.payment_mode = "MOCK"
    if body.outcome == "success":
        slot.confirmed_guests += booking.guest_count
        booking.status = "CONFIRMED"
        for number in range(1, booking.guest_count + 1):
            session.add(
                GuestTicket(
                    booking_id=booking.id,
                    guest_number=number,
                    reference="MOCK-" + uuid4().hex.upper(),
                )
            )
        emit(session, booking, "MockBookingConfirmed")
    else:
        booking.status = "PAYMENT_FAILED"
        emit(session, booking, "MockBookingPaymentFailed")
    session.flush()
    return booking


def router(session_dependency, now, emit, expire_slot):
    from typing import Annotated

    from fastapi import Depends
    from sqlalchemy.orm import Session

    from booking_app.schemas import BookingResponse, TicketResponse

    api = APIRouter(prefix="/api/v1/bookings")
    DatabaseSession = Annotated[Session, Depends(session_dependency)]

    @api.post("/{booking_id}/mock-payment", response_model=BookingResponse)
    def simulate(booking_id: UUID, body: MockOutcome, user: CurrentUser, session: DatabaseSession):
        if not get_settings().mock_payments_enabled:
            raise HTTPException(404, "Mock payment simulation is disabled")
        with session.begin():
            return BookingResponse.model_validate(
                settle(session, booking_id, user.user_id, body, now(), emit, expire_slot)
            )

    @api.get("/{booking_id}/tickets", response_model=list[TicketResponse])
    def tickets(booking_id: UUID, user: CurrentUser, session: DatabaseSession):
        with session.begin():
            booking = session.scalar(
                select(Booking).where(Booking.id == booking_id, Booking.user_sub == user.user_id)
            )
            if booking is None:
                raise HTTPException(404, "Booking not found")
            if booking.status != "CONFIRMED":
                raise HTTPException(409, "Tickets are issued only after confirmation.")
            return [
                TicketResponse.model_validate(row)
                for row in session.scalars(
                    select(GuestTicket)
                    .where(GuestTicket.booking_id == booking.id)
                    .order_by(GuestTicket.guest_number)
                )
            ]

    return api
