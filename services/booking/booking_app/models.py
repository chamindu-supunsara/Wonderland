from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from booking_app.db import Base


class VisitSlot(Base):
    __tablename__ = "visit_slots"
    __table_args__ = (
        UniqueConstraint("visit_date", "starts_at"),
        CheckConstraint("ends_at > starts_at"),
        CheckConstraint("capacity_guests > 0 AND held_guests >= 0 AND confirmed_guests >= 0"),
        CheckConstraint("held_guests + confirmed_guests <= capacity_guests"),
        {"schema": "booking"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    visit_date: Mapped[date] = mapped_column(index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity_guests: Mapped[int] = mapped_column(Integer)
    held_guests: Mapped[int] = mapped_column(default=0, server_default="0")
    confirmed_guests: Mapped[int] = mapped_column(default=0, server_default="0")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("user_sub", "idempotency_key"),
        CheckConstraint("guest_count BETWEEN 1 AND 5 AND amount_minor > 0 AND price_version > 0"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT','CANCELLED','EXPIRED','CONFIRMED','PAYMENT_FAILED')"
        ),
        {"schema": "booking"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    user_sub: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("booking.visit_slots.id"), index=True)
    visit_date: Mapped[date]
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tier_id: Mapped[UUID]
    tier_code: Mapped[str] = mapped_column(String(20))
    tier_name: Mapped[str] = mapped_column(String(80))
    guest_count: Mapped[int]
    amount_minor: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    price_version: Mapped[int]
    status: Mapped[str] = mapped_column(String(30), default="PENDING_PAYMENT")
    payment_mode: Mapped[str] = mapped_column(String(12), default="NONE", server_default="NONE")
    event_version: Mapped[int] = mapped_column(default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "booking"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("booking.bookings.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    aggregate_id: Mapped[UUID]
    aggregate_version: Mapped[int]
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sns_message_id: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(120))


class MockSettlement(Base):
    __tablename__ = "mock_settlements"
    __table_args__ = ({"schema": "booking"},)
    checkout_id: Mapped[UUID] = mapped_column(primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("booking.bookings.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuestTicket(Base):
    __tablename__ = "guest_tickets"
    __table_args__ = (UniqueConstraint("booking_id", "guest_number"), {"schema": "booking"})
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("booking.bookings.id"))
    guest_number: Mapped[int]
    reference: Mapped[str] = mapped_column(String(45), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
