from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookingWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier_id: UUID
    slot_id: UUID
    guest_count: int = Field(strict=True, ge=1, le=5)
    expected_price_version: int = Field(strict=True, ge=1)


class SlotWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visit_date: date
    start_time: time
    end_time: time
    capacity_guests: int = Field(strict=True, ge=1, le=10000)

    @field_validator("start_time", "end_time")
    @classmethod
    def local_minute(cls, value):
        if value.tzinfo or value.second or value.microsecond:
            raise ValueError("Use local HH:MM times without seconds or timezone")
        return value


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    visit_date: date
    starts_at: datetime
    ends_at: datetime
    capacity_guests: int
    held_guests: int
    confirmed_guests: int
    remaining_guests: int
    timezone: str = "Asia/Colombo"


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    slot_id: UUID
    visit_date: date
    starts_at: datetime
    ends_at: datetime
    tier_id: UUID
    tier_code: str
    tier_name: str
    guest_count: int
    amount_minor: int
    currency: str
    price_version: int
    status: Literal["PENDING_PAYMENT", "CANCELLED", "EXPIRED", "CONFIRMED", "PAYMENT_FAILED"]
    payment_mode: Literal["NONE", "MOCK"] = "NONE"
    expires_at: datetime
    created_at: datetime
    timezone: str = "Asia/Colombo"


class TierQuote(BaseModel):
    id: UUID
    code: str
    name: str
    min_guests: int = Field(ge=1, le=5)
    max_guests: int = Field(ge=1, le=5)
    amount_minor: int = Field(strict=True, gt=0)
    currency: Literal["USD"]
    price_version: int = Field(strict=True, gt=0)


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    booking_id: UUID
    guest_number: int
    reference: str
    issued_at: datetime
    is_mock: Literal[True] = True
