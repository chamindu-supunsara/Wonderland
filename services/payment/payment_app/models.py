from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from payment_app.db import Base


class Checkout(Base):
    __tablename__ = "mock_checkouts"
    __table_args__ = (
        CheckConstraint("status IN ('READY','DECIDED','SUCCEEDED','FAILED','REJECTED')"),
        CheckConstraint("amount_minor > 0"),
        {"schema": "payment"},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    booking_id: Mapped[UUID] = mapped_column(unique=True)
    user_sub: Mapped[str] = mapped_column(String(128), index=True)
    amount_minor: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    booking_reference: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(15), default="READY")
    outcome: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
