from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Attraction(Base):
    __tablename__ = "attractions"
    __table_args__ = (
        CheckConstraint("min_age IS NULL OR min_age >= 0", name="ck_attraction_age"),
        CheckConstraint("min_height_cm IS NULL OR min_height_cm >= 0", name="ck_attraction_height"),
        CheckConstraint("status IN ('ACTIVE', 'RETIRED')", name="ck_attraction_status"),
        CheckConstraint("revision > 0", name="ck_attraction_revision"),
        UniqueConstraint("seed_key", name="uq_attraction_seed_key"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    seed_key: Mapped[str | None] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), index=True)
    thrill_level: Mapped[str] = mapped_column(String(20))
    min_age: Mapped[int | None] = mapped_column(Integer)
    min_height_cm: Mapped[int | None] = mapped_column(Integer)
    guidance_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TicketTier(Base):
    __tablename__ = "ticket_tiers"
    __table_args__ = (
        CheckConstraint("min_guests >= 1 AND max_guests >= min_guests", name="ck_tier_guests"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    min_guests: Mapped[int] = mapped_column(Integer)
    max_guests: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)
    prices: Mapped[list["TicketPrice"]] = relationship(back_populates="tier")


class TicketPrice(Base):
    __tablename__ = "ticket_prices"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_price_positive"),
        CheckConstraint("version > 0", name="ck_price_version"),
        UniqueConstraint("tier_id", "version", name="uq_tier_price_version"),
        Index(
            "uq_one_active_price_per_tier",
            "tier_id",
            unique=True,
            postgresql_where=text("active = true"),
        ),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tier_id: Mapped[UUID] = mapped_column(ForeignKey("catalog.ticket_tiers.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tier: Mapped[TicketTier] = relationship(back_populates="prices")


class CatalogAudit(Base):
    __tablename__ = "audit_events"
    __table_args__ = ({"schema": "catalog"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[UUID] = mapped_column(index=True)
    changes: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CatalogOutbox(Base):
    __tablename__ = "outbox_events"
    __table_args__ = ({"schema": "catalog"},)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    aggregate_id: Mapped[UUID]
    aggregate_version: Mapped[int]
    event_type: Mapped[str] = mapped_column(String(80))
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
