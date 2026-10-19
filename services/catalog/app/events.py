"""Write full, versioned package snapshots in the price transaction."""

from sqlalchemy import select

from app.models import CatalogOutbox, TicketPrice, TicketTier


def price_event(session, tier, price):
    session.add(
        CatalogOutbox(
            aggregate_id=tier.id,
            aggregate_version=price.version,
            event_type="TicketPricePublished",
            payload={
                "id": str(tier.id),
                "code": tier.code,
                "name": tier.name,
                "min_guests": tier.min_guests,
                "max_guests": tier.max_guests,
                "active": tier.active,
                "amount_minor": price.amount_minor,
                "currency": price.currency,
                "price_version": price.version,
            },
        )
    )


def snapshot_current_prices(factory):
    # Bootstrap/recovery through the normal outbox. Full snapshots tolerate repeated enqueueing.
    with factory.begin() as session:
        for tier in session.scalars(select(TicketTier).order_by(TicketTier.id).with_for_update()):
            price = session.scalar(
                select(TicketPrice).where(
                    TicketPrice.tier_id == tier.id, TicketPrice.active.is_(True)
                )
            )
            if price:
                price_event(session, tier, price)
