from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from admission_app.db import Base


class Ticket(Base):
    __tablename__ = "ticket_projection"
    __table_args__ = {"schema": "admission"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(45), unique=True)
    booking_id: Mapped[UUID] = mapped_column(index=True)
    booking_reference: Mapped[str] = mapped_column(String(40))
    user_sub: Mapped[str] = mapped_column(String(128), index=True)
    guest_number: Mapped[int]
    tier_code: Mapped[str] = mapped_column(String(20))
    tier_name: Mapped[str] = mapped_column(String(80))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Admission(Base):
    __tablename__ = "check_ins"
    __table_args__ = {"schema": "admission"}
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission.ticket_projection.id"), unique=True
    )
    actor_sub: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    event_version: Mapped[int] = mapped_column(default=1)


class RideUse(Base):
    __tablename__ = "ride_uses"
    __table_args__ = (UniqueConstraint("actor_sub", "idempotency_key"), {"schema": "admission"})
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    admission_id: Mapped[UUID] = mapped_column(ForeignKey("admission.check_ins.id"), index=True)
    attraction_id: Mapped[UUID]
    attraction_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    actor_sub: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("aggregate_id", "aggregate_version"),
        {"schema": "admission"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    aggregate_id: Mapped[UUID]
    aggregate_version: Mapped[int]
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sns_message_id: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(120))
