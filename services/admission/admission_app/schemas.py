from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class TicketSnapshot(BaseModel):
    id: UUID
    reference: str = Field(pattern=r"^MOCK-[A-F0-9]{32}$")
    booking_id: UUID
    booking_reference: str = Field(min_length=1, max_length=40)
    user_sub: str = Field(min_length=1, max_length=128)
    guest_number: int = Field(strict=True, ge=1, le=5)
    tier_code: str = Field(min_length=1, max_length=20)
    tier_name: str = Field(min_length=1, max_length=80)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    status: Literal["CONFIRMED"]
    payment_mode: Literal["MOCK"]

    @model_validator(mode="after")
    def ordered(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("Invalid visit slot")
        return self


class CheckInWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_reference: str = Field(pattern=r"^MOCK-[A-F0-9]{32}$")
    simulation_time: AwareDatetime

    @field_validator("simulation_time")
    @classmethod
    def utc_time(cls, value):
        return value.astimezone(UTC)


class RideWrite(CheckInWrite):
    attraction_id: UUID


class RideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    attraction_id: UUID
    attraction_name: str
    category: str
    occurred_at: datetime
    recorded_at: datetime
    mode: Literal["MOCK"] = "MOCK"
