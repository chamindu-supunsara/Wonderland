from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas import AttractionResponse, TierResponse

Category = Literal["ROLLER_COASTER", "KIDS", "WATER", "INTERACTIVE"]
Thrill = Literal["LOW", "MEDIUM", "HIGH"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]
Guidance = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AttractionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Description
    category: Category
    thrill_level: Thrill
    min_age: Annotated[int, Field(strict=True, ge=0, le=120)] | None = None
    min_height_cm: Annotated[int, Field(strict=True, ge=0, le=300)] | None = None
    guidance_text: Guidance


class AttractionEdit(AttractionWrite):
    expected_revision: int = Field(strict=True, ge=1)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(strict=True, ge=1)


class AdminAttractionResponse(AttractionResponse):
    status: Literal["ACTIVE", "RETIRED"]
    revision: int
    created_at: datetime
    updated_at: datetime


class PriceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_minor: int = Field(strict=True, ge=1, le=100_000_000)
    expected_version: int = Field(strict=True, ge=1)


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    amount_minor: int
    currency: str
    version: int
    active: bool
    created_at: datetime
    created_by: str | None


class AdminTierResponse(TierResponse):
    active: bool


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: str
    action: str
    resource_id: UUID
    changes: dict
    created_at: datetime
