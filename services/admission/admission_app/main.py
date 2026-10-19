import hashlib
import json
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admission_app.auth import Administrator, CurrentUser
from admission_app.config import get_settings
from admission_app.db import get_session
from admission_app.models import Admission, OutboxEvent, RideUse, Ticket
from admission_app.schemas import CheckInWrite, RideResponse, RideWrite
from admission_app.upstream import get_attraction, get_ticket

DatabaseSession = Annotated[Session, Depends(get_session)]
Reference = Annotated[str, Path(pattern=r"^MOCK-[A-F0-9]{32}$")]


def gate():
    if not get_settings().mock_admission_enabled:
        raise HTTPException(404, "Mock admission is disabled")


def lock(session, key):
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": key})


def project(session, snapshot):
    lock(session, f"ticket:{snapshot.id}")
    values = snapshot.model_dump(exclude={"status", "payment_mode"})
    ticket = session.get(Ticket, snapshot.id)
    if ticket is None:
        ticket = Ticket(**values)
        session.add(ticket)
        session.flush()
    elif any(getattr(ticket, name) != value for name, value in values.items()):
        raise HTTPException(
            409, "The confirmed ticket snapshot changed; investigate before admission."
        )
    return ticket


def validate_time(ticket, simulation_time, earliest=None):
    if not ticket.starts_at <= simulation_time < ticket.ends_at:
        raise HTTPException(422, "Simulation time must be within the booked slot (end exclusive).")
    if earliest is not None and simulation_time < earliest:
        raise HTTPException(422, "Ride usage cannot precede guest check-in.")


def public_ticket(ticket):
    return {
        name: getattr(ticket, name)
        for name in (
            "id",
            "reference",
            "booking_id",
            "booking_reference",
            "guest_number",
            "tier_code",
            "tier_name",
            "starts_at",
            "ends_at",
        )
    }


def visit_view(session, admission, ticket):
    return {
        "id": admission.id,
        "ticket": public_ticket(ticket),
        "mode": "MOCK",
        "occurred_at": admission.occurred_at,
        "recorded_at": admission.recorded_at,
        "ride_count": session.scalar(
            select(func.count()).select_from(RideUse).where(RideUse.admission_id == admission.id)
        ),
    }


def emit(session, admission, ticket, kind, ride=None):
    payload = {
        "admission_id": str(admission.id),
        "ticket_id": str(ticket.id),
        "booking_id": str(ticket.booking_id),
        "user_sub": ticket.user_sub,
        "guest_number": ticket.guest_number,
        "tier_code": ticket.tier_code,
        "mode": "MOCK",
        "occurred_at": (ride or admission).occurred_at.isoformat(),
        "recorded_at": (ride or admission).recorded_at.isoformat(),
    }
    if ride:
        payload.update(
            ride_id=str(ride.id),
            attraction_id=str(ride.attraction_id),
            attraction_name=ride.attraction_name,
            category=ride.category,
        )
    session.add(
        OutboxEvent(
            aggregate_id=admission.id,
            aggregate_version=admission.event_version,
            event_type=kind,
            payload=payload,
        )
    )
    session.flush()


def replay_ride(session, actor, key, digest):
    row = session.scalar(
        select(RideUse).where(RideUse.actor_sub == actor, RideUse.idempotency_key == key)
    )
    if row is not None and row.request_hash != digest:
        raise HTTPException(409, "This retry key belongs to a different ride request.")
    return row


def create_app():
    app = FastAPI(title="Wonderland MOCK Admission", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health/live")
    def live():
        return {
            "status": "ok",
            "service": "admission",
            "mode": "MOCK",
            "mock_enabled": get_settings().mock_admission_enabled,
        }

    @app.get("/health/ready")
    def ready(session: DatabaseSession):
        try:
            session.execute(text("SELECT id FROM admission.check_ins LIMIT 1"))
            session.execute(text("SELECT id FROM admission.ride_uses LIMIT 1"))
            session.execute(text("SELECT published_at FROM admission.outbox_events LIMIT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(503, "Admission storage is not ready") from exc
        return {"status": "ready", "service": "admission", "mode": "MOCK"}

    @app.get("/api/v1/admissions/staff/tickets/{reference}")
    def lookup(
        reference: Reference,
        staff: Administrator,
        session: DatabaseSession,
        authorization: Annotated[str, Header()],
    ):
        gate()
        ticket = get_ticket(reference, authorization)
        admission = session.scalar(select(Admission).where(Admission.ticket_id == ticket.id))
        rides = (
            []
            if admission is None
            else session.scalars(
                select(RideUse)
                .where(RideUse.admission_id == admission.id)
                .order_by(RideUse.occurred_at.desc(), RideUse.id.desc())
                .limit(20)
            ).all()
        )
        return {
            "ticket": public_ticket(ticket),
            "mode": "MOCK",
            "check_in": visit_view(session, admission, ticket) if admission else None,
            "recent_rides": [RideResponse.model_validate(row) for row in rides],
        }

    @app.post("/api/v1/admissions/staff/check-ins")
    def check_in(
        body: CheckInWrite,
        staff: Administrator,
        session: DatabaseSession,
        authorization: Annotated[str, Header()],
        response: Response,
    ):
        gate()
        snapshot = get_ticket(body.ticket_reference, authorization)
        with session.begin():
            ticket = project(session, snapshot)
            admission = session.scalar(select(Admission).where(Admission.ticket_id == ticket.id))
            if admission:
                return {**visit_view(session, admission, ticket), "already_checked_in": True}
            validate_time(ticket, body.simulation_time)
            admission = Admission(
                ticket_id=ticket.id,
                actor_sub=staff.user_id,
                occurred_at=body.simulation_time,
                event_version=1,
            )
            session.add(admission)
            session.flush()
            emit(session, admission, ticket, "MockGuestCheckedIn")
            response.status_code = 201
            return {**visit_view(session, admission, ticket), "already_checked_in": False}

    @app.post("/api/v1/admissions/staff/ride-uses", response_model=RideResponse)
    def ride_use(
        body: RideWrite,
        staff: Administrator,
        session: DatabaseSession,
        idempotency_key: Annotated[UUID, Header()],
        response: Response,
    ):
        gate()
        digest = hashlib.sha256(
            json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        with session.begin():
            replay = replay_ride(session, staff.user_id, idempotency_key, digest)
            if replay:
                return RideResponse.model_validate(replay)
        attraction = get_attraction(
            body.attraction_id
        )  # Active-only Catalog endpoint, fail closed.
        with session.begin():
            lock(session, f"ride:{staff.user_id}:{idempotency_key}")
            replay = replay_ride(session, staff.user_id, idempotency_key, digest)
            if replay:
                return RideResponse.model_validate(replay)
            pair = session.execute(
                select(Admission, Ticket)
                .join(Ticket, Ticket.id == Admission.ticket_id)
                .where(Ticket.reference == body.ticket_reference)
                .with_for_update(of=Admission)
            ).first()
            if pair is None:
                raise HTTPException(409, "Check this guest in before recording a ride.")
            admission, ticket = pair
            validate_time(ticket, body.simulation_time, admission.occurred_at)
            ride = RideUse(
                admission_id=admission.id,
                attraction_id=attraction.id,
                attraction_name=attraction.name,
                category=attraction.category,
                actor_sub=staff.user_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                occurred_at=body.simulation_time,
            )
            session.add(ride)
            admission.event_version += 1
            session.flush()
            emit(session, admission, ticket, "MockRideUsed", ride)
            response.status_code = 201
            return RideResponse.model_validate(ride)

    @app.get("/api/v1/admissions/visits/me")
    def history(
        user: CurrentUser,
        session: DatabaseSession,
        limit: Annotated[int, Query(ge=1, le=20)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    ):
        gate()
        pairs = session.execute(
            select(Admission, Ticket)
            .join(Ticket, Ticket.id == Admission.ticket_id)
            .where(Ticket.user_sub == user.user_id)
            .order_by(Admission.occurred_at.desc(), Admission.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [visit_view(session, admission, ticket) for admission, ticket in pairs]

    @app.get("/api/v1/admissions/visits/{visit_id}/rides", response_model=list[RideResponse])
    def own_rides(
        visit_id: UUID,
        user: CurrentUser,
        session: DatabaseSession,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    ):
        gate()
        owned = session.scalar(
            select(Admission.id)
            .join(Ticket, Ticket.id == Admission.ticket_id)
            .where(Admission.id == visit_id, Ticket.user_sub == user.user_id)
        )
        if owned is None:
            raise HTTPException(404, "Visit not found")
        return session.scalars(
            select(RideUse)
            .where(RideUse.admission_id == visit_id)
            .order_by(RideUse.occurred_at.desc(), RideUse.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()

    return app


app = create_app()
