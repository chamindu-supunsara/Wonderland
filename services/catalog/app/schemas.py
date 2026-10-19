from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    category: str
    thrill_level: str
    min_age: int | None
    min_height_cm: int | None
    guidance_text: str


class TierResponse(BaseModel):
    id: UUID
    code: str
    name: str
    min_guests: int
    max_guests: int
    amount_minor: int
    currency: str
    price_version: int
