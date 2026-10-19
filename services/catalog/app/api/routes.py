from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Attraction, TicketPrice, TicketTier
from app.schemas import AttractionResponse, TierResponse

router = APIRouter(prefix="/api/v1", tags=["catalog"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("/attractions", response_model=list[AttractionResponse])
def list_attractions(
    session: DatabaseSession,
    category: Annotated[str | None, Query(max_length=40)] = None,
):
    statement = select(Attraction).where(Attraction.status == "ACTIVE")
    if category:
        statement = statement.where(Attraction.category == category)
    return session.scalars(statement.order_by(Attraction.name)).all()


@router.get("/attractions/{attraction_id}", response_model=AttractionResponse)
def get_attraction(attraction_id: UUID, session: DatabaseSession):
    attraction = session.scalar(
        select(Attraction).where(Attraction.id == attraction_id, Attraction.status == "ACTIVE")
    )
    if attraction is None:
        raise HTTPException(status_code=404, detail="Attraction not found")
    return attraction


@router.get("/ticket-tiers", response_model=list[TierResponse])
def list_ticket_tiers(session: DatabaseSession):
    rows = session.execute(
        select(TicketTier, TicketPrice)
        .join(TicketPrice)
        .where(TicketTier.active.is_(True), TicketPrice.active.is_(True))
        .order_by(TicketTier.max_guests, TicketTier.code)
    ).all()
    return [
        TierResponse(
            id=tier.id,
            code=tier.code,
            name=tier.name,
            min_guests=tier.min_guests,
            max_guests=tier.max_guests,
            amount_minor=price.amount_minor,
            currency=price.currency,
            price_version=price.version,
        )
        for tier, price in rows
    ]
