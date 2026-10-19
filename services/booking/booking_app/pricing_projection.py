import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from booking_app.schemas import TierQuote


def apply_price(session, event):
    if event.source != "catalog" or event.event_type != "TicketPricePublished":
        raise ValueError("Unexpected pricing event")
    quote = TierQuote.model_validate(event.data)
    if (
        quote.id != event.aggregate_id
        or quote.price_version != event.aggregate_version
        or type(event.data.get("active")) is not bool
        or quote.min_guests > quote.max_guests
    ):
        raise ValueError("Invalid pricing snapshot")
    session.execute(
        text("""
        INSERT INTO booking.ticket_price_projection(tier_id,version,payload)
        VALUES(:id,:version,CAST(:payload AS jsonb))
        ON CONFLICT(tier_id) DO UPDATE SET version=EXCLUDED.version,payload=EXCLUDED.payload,
        received_at=now() WHERE ticket_price_projection.version < EXCLUDED.version
    """),
        {"id": quote.id, "version": quote.price_version, "payload": json.dumps(event.data)},
    )


def projected_quote(session, tier_id: UUID):
    data = session.execute(
        text("SELECT payload FROM booking.ticket_price_projection WHERE tier_id=:id"),
        {"id": tier_id},
    ).scalar()
    if data is None:
        raise HTTPException(503, "Pricing has not synchronized yet. Try again shortly.")
    if not data["active"]:
        raise HTTPException(409, "This ticket tier is no longer available.")
    return TierQuote.model_validate(data)
