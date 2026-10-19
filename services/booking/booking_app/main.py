import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from booking_app.auth import Administrator, CurrentUser
from booking_app.catalog import get_quote
from booking_app.config import get_settings
from booking_app.db import get_session
from booking_app.mock_checkout import router as mock_router
from booking_app.models import Booking, GuestTicket, OutboxEvent, VisitSlot
from booking_app.pricing_projection import projected_quote
from booking_app.schemas import BookingResponse, BookingWrite, SlotResponse, SlotWrite

PARK_ZONE = ZoneInfo("Asia/Colombo")
DatabaseSession = Annotated[Session, Depends(get_session)]


def now():
    return datetime.now(UTC)


def validate_date(value: date):
    today = now().astimezone(PARK_ZONE).date()
    if not today <= value <= today + timedelta(days=90):
        raise HTTPException(422, "Choose a park date from today through the next 90 days.")


def slot_response(slot):
    return SlotResponse(
        **{
            name: getattr(slot, name)
            for name in SlotResponse.model_fields
            if name not in {"remaining_guests", "timezone"}
        },
        remaining_guests=slot.capacity_guests - slot.held_guests - slot.confirmed_guests,
    )


def event(session, booking, kind):
    booking.event_version += 1
    session.add(
        OutboxEvent(
            booking_id=booking.id,
            aggregate_id=booking.id,
            aggregate_version=booking.event_version,
            event_type=kind,
            payload={
                **BookingResponse.model_validate(booking).model_dump(mode="json"),
                "user_sub": booking.user_sub,
            },
        )
    )


def expire_slot(session, slot, timestamp):
    # Caller holds the slot lock. All capacity transitions acquire this lock first.
    expired = session.scalars(
        select(Booking)
        .where(
            Booking.slot_id == slot.id,
            Booking.status == "PENDING_PAYMENT",
            Booking.expires_at <= timestamp,
        )
        .with_for_update()
    ).all()
    for booking in expired:
        slot.held_guests -= booking.guest_count
        booking.status = "EXPIRED"
        event(session, booking, "BookingExpired")
    session.flush()


def expire_holds(session):
    timestamp = now()
    ids = session.scalars(
        select(Booking.slot_id)
        .where(
            Booking.status == "PENDING_PAYMENT",
            Booking.expires_at <= timestamp,
        )
        .distinct()
        .order_by(Booking.slot_id)
    ).all()
    for slot_id in ids:
        slot = session.scalar(select(VisitSlot).where(VisitSlot.id == slot_id).with_for_update())
        expire_slot(session, slot, timestamp)


def create_slot(session, body):
    validate_date(body.visit_date)
    start = datetime.combine(body.visit_date, body.start_time, PARK_ZONE)
    end = datetime.combine(body.visit_date, body.end_time, PARK_ZONE)
    if end <= start or start <= now():
        raise HTTPException(422, "Slot must start in the future and end later on the same day.")
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"slots:{body.visit_date}"},
    )
    overlap = session.scalar(
        select(VisitSlot.id).where(
            VisitSlot.visit_date == body.visit_date,
            VisitSlot.starts_at < end,
            VisitSlot.ends_at > start,
        )
    )
    if overlap:
        raise HTTPException(409, "A slot already overlaps this time window.")
    slot = VisitSlot(
        visit_date=body.visit_date,
        starts_at=start,
        ends_at=end,
        capacity_guests=body.capacity_guests,
    )
    session.add(slot)
    session.flush()
    return slot


def create_app():
    settings = get_settings()
    app = FastAPI(title="Wonderland Booking", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def private_responses(request, call_next):
        result = await call_next(request)
        if request.url.path.startswith("/api/"):
            result.headers["Cache-Control"] = "no-store"
        return result

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "booking"}

    @app.get("/health/ready")
    def ready(session: DatabaseSession):
        try:
            session.execute(text("SELECT held_guests FROM booking.visit_slots LIMIT 1"))
            session.execute(text("SELECT request_hash FROM booking.bookings LIMIT 1"))
            session.execute(text("SELECT aggregate_version FROM booking.outbox_events LIMIT 1"))
            session.execute(text("SELECT id FROM booking.guest_tickets LIMIT 1"))
            if settings.pricing_mode == "projection":
                session.execute(text("SELECT version FROM booking.ticket_price_projection LIMIT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(503, "Booking storage is not ready") from exc
        return {"status": "ready", "service": "booking"}

    @app.get("/api/v1/booking-policy")
    def policy(user: CurrentUser):
        today = now().astimezone(PARK_ZONE).date()
        return {
            "timezone": "Asia/Colombo",
            "today": today,
            "last_date": today + timedelta(days=90),
            "hold_minutes": 30,
        }

    @app.get("/api/v1/visit-slots", response_model=list[SlotResponse])
    def slots(user: CurrentUser, session: DatabaseSession, date: date):
        validate_date(date)
        with session.begin():
            expire_holds(session)
            rows = session.scalars(
                select(VisitSlot)
                .where(
                    VisitSlot.visit_date == date,
                    VisitSlot.starts_at > now(),
                )
                .order_by(VisitSlot.starts_at)
            ).all()
            return [slot_response(row) for row in rows]

    @app.post("/api/v1/admin/visit-slots", response_model=SlotResponse, status_code=201)
    def add_slot(body: SlotWrite, user: Administrator, session: DatabaseSession):
        with session.begin():
            return slot_response(create_slot(session, body))

    @app.post("/api/v1/bookings", response_model=BookingResponse, status_code=201)
    def book(
        body: BookingWrite,
        user: CurrentUser,
        session: DatabaseSession,
        response: Response,
        idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    ):
        fingerprint = hashlib.sha256(
            json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        with session.begin():
            # Serializes retries per owner/key across API replicas, before checking existence.
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"booking:{user.user_id}:{idempotency_key}"},
            )
            existing = session.scalar(
                select(Booking).where(
                    Booking.user_sub == user.user_id, Booking.idempotency_key == idempotency_key
                )
            )
            if existing:
                if existing.request_hash != fingerprint:
                    raise HTTPException(409, "Idempotency key was used for a different request.")
                response.status_code = 200
                return BookingResponse.model_validate(existing)
            if settings.pricing_mode == "projection":
                quote = projected_quote(session, body.tier_id)
            elif settings.pricing_mode == "http":
                quote = get_quote(body.tier_id)
            else:
                raise HTTPException(503, "Invalid pricing configuration")
            if quote.price_version != body.expected_price_version:
                raise HTTPException(409, "The price changed. Reload prices and review again.")
            if not quote.min_guests <= body.guest_count <= quote.max_guests:
                raise HTTPException(422, "Guest count does not match the selected package.")
            slot = session.scalar(
                select(VisitSlot).where(VisitSlot.id == body.slot_id).with_for_update()
            )
            if slot is None:
                raise HTTPException(404, "Time slot not found")
            timestamp = now()
            validate_date(slot.visit_date)
            if slot.starts_at <= timestamp:
                raise HTTPException(409, "This time slot has already started.")
            expire_slot(session, slot, timestamp)
            if slot.held_guests + slot.confirmed_guests + body.guest_count > slot.capacity_guests:
                raise HTTPException(
                    409, "This slot has insufficient capacity. Choose another slot."
                )
            slot.held_guests += body.guest_count
            booking = Booking(
                id=uuid4(),
                reference="WL-" + uuid4().hex.upper(),
                user_sub=user.user_id,
                idempotency_key=idempotency_key,
                request_hash=fingerprint,
                slot_id=slot.id,
                visit_date=slot.visit_date,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                tier_id=quote.id,
                tier_code=quote.code,
                tier_name=quote.name,
                guest_count=body.guest_count,
                amount_minor=quote.amount_minor,
                currency=quote.currency,
                price_version=quote.price_version,
                expires_at=timestamp + timedelta(minutes=30),
                payment_mode="MOCK" if settings.mock_payments_enabled else "NONE",
            )
            session.add(booking)
            session.flush()
            event(session, booking, "BookingPaymentRequested")
            return BookingResponse.model_validate(booking)

    @app.get("/api/v1/bookings/me", response_model=list[BookingResponse])
    def history(
        user: CurrentUser,
        session: DatabaseSession,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        with session.begin():
            expire_holds(session)
            return [
                BookingResponse.model_validate(row)
                for row in session.scalars(
                    select(Booking)
                    .where(Booking.user_sub == user.user_id)
                    .order_by(Booking.created_at.desc(), Booking.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ]

    @app.get("/api/v1/bookings/{booking_id}", response_model=BookingResponse)
    def detail(booking_id: UUID, user: CurrentUser, session: DatabaseSession):
        with session.begin():
            expire_holds(session)
            booking = session.scalar(
                select(Booking).where(Booking.id == booking_id, Booking.user_sub == user.user_id)
            )
            if booking is None:
                raise HTTPException(404, "Booking not found")
            return BookingResponse.model_validate(booking)

    @app.post("/api/v1/bookings/{booking_id}/cancel", response_model=BookingResponse)
    def cancel(booking_id: UUID, user: CurrentUser, session: DatabaseSession):
        with session.begin():
            owned = session.scalar(
                select(Booking).where(Booking.id == booking_id, Booking.user_sub == user.user_id)
            )
            if owned is None:
                raise HTTPException(404, "Booking not found")
            slot = session.scalar(
                select(VisitSlot).where(VisitSlot.id == owned.slot_id).with_for_update()
            )
            expire_slot(session, slot, now())
            booking = session.scalar(
                select(Booking)
                .where(Booking.id == booking_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if booking.status == "CONFIRMED":
                raise HTTPException(409, "Confirmed mock bookings cannot be cancelled here.")
            if booking.status == "PENDING_PAYMENT":
                slot.held_guests -= booking.guest_count
                booking.status = "CANCELLED"
                event(session, booking, "BookingCancelled")
            return BookingResponse.model_validate(booking)

    @app.get("/api/v1/admin/mock-tickets/{reference}")
    def staff_mock_ticket(
        reference: Annotated[str, Path(pattern=r"^MOCK-[A-F0-9]{32}$")],
        staff: Administrator,
        session: DatabaseSession,
    ):
        if not get_settings().mock_payments_enabled:
            raise HTTPException(404, "Mock tickets are disabled")
        pair = session.execute(
            select(GuestTicket, Booking)
            .join(Booking)
            .where(
                GuestTicket.reference == reference,
                Booking.status == "CONFIRMED",
                Booking.payment_mode == "MOCK",
            )
        ).first()
        if pair is None:
            raise HTTPException(404, "Confirmed mock ticket not found")
        ticket, booking = pair
        return {
            "id": ticket.id,
            "reference": ticket.reference,
            "booking_id": booking.id,
            "booking_reference": booking.reference,
            "user_sub": booking.user_sub,
            "guest_number": ticket.guest_number,
            "tier_code": booking.tier_code,
            "tier_name": booking.tier_name,
            "starts_at": booking.starts_at,
            "ends_at": booking.ends_at,
            "status": booking.status,
            "payment_mode": booking.payment_mode,
        }

    app.include_router(mock_router(get_session, lambda: now(), event, expire_slot))
    return app


app = create_app()
