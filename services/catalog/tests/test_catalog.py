from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import Attraction, TicketPrice, TicketTier


def add_attraction(session, *, name="Test Coaster", status="ACTIVE", category="ROLLER_COASTER"):
    attraction = Attraction(
        name=name,
        description="A test ride",
        category=category,
        thrill_level="HIGH",
        min_age=12,
        min_height_cm=140,
        guidance_text="Follow staff instructions",
        status=status,
    )
    session.add(attraction)
    session.flush()
    return attraction


def test_browse_hides_retired_attractions_and_filters_category(client, session):
    add_attraction(session)
    add_attraction(session, name="Old Ride", status="RETIRED")
    add_attraction(session, name="Water Ride", category="WATER")
    response = client.get("/api/v1/attractions")
    assert response.status_code == 200
    assert [ride["name"] for ride in response.json()] == ["Test Coaster", "Water Ride"]
    filtered = client.get("/api/v1/attractions", params={"category": "WATER"})
    assert [ride["name"] for ride in filtered.json()] == ["Water Ride"]


def test_attraction_details_include_suitability(client, session):
    attraction = add_attraction(session)
    response = client.get(f"/api/v1/attractions/{attraction.id}")
    assert response.status_code == 200
    assert response.json()["min_height_cm"] == 140
    assert response.json()["min_age"] == 12


def test_retired_or_missing_attraction_is_not_public(client, session):
    retired = add_attraction(session, status="RETIRED")
    assert client.get(f"/api/v1/attractions/{retired.id}").status_code == 404
    assert client.get(f"/api/v1/attractions/{uuid4()}").status_code == 404
    assert client.get("/api/v1/attractions/not-a-uuid").status_code == 422


def test_tiers_expose_only_active_price_and_integer_money(client, session):
    tier = TicketTier(code="FAMILY", name="Family", min_guests=1, max_guests=4)
    session.add(tier)
    session.flush()
    session.add_all(
        [
            TicketPrice(tier_id=tier.id, amount_minor=13000, version=1, active=False),
            TicketPrice(tier_id=tier.id, amount_minor=14000, version=2),
        ]
    )
    session.flush()
    response = client.get("/api/v1/ticket-tiers")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["amount_minor"] == 14000
    assert response.json()[0]["price_version"] == 2
    tier.active = False
    session.flush()
    assert client.get("/api/v1/ticket-tiers").json() == []


def test_postgres_prevents_two_active_prices_for_one_tier(session):
    tier = TicketTier(code="COUPLE", name="Couple", min_guests=2, max_guests=2)
    session.add(tier)
    session.flush()
    session.add(TicketPrice(tier_id=tier.id, amount_minor=7500, version=1))
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(TicketPrice(tier_id=tier.id, amount_minor=8000, version=2))
        session.flush()


def test_postgres_rejects_invalid_guest_range(session):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(TicketTier(code="INVALID", name="Invalid", min_guests=3, max_guests=2))
        session.flush()


def test_readiness_checks_real_storage(client, session):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    # Roll back the temporary rename at the end of the test.
    session.execute(text("ALTER TABLE catalog.ticket_prices RENAME TO unavailable_prices"))
    assert client.get("/health/ready").status_code == 503


def test_seed_is_repeatable_and_preserves_existing_prices(session, monkeypatch):
    from app import seed as seed_module

    monkeypatch.setattr(
        seed_module,
        "session_factory",
        lambda: sessionmaker(bind=session.connection(), join_transaction_mode="create_savepoint"),
    )
    seed_module.seed()
    seed_module.seed()
    assert session.scalar(select(func.count()).select_from(Attraction)) == 4
    assert session.scalar(select(func.count()).select_from(TicketTier)) == 4
    price = session.scalar(select(TicketPrice).where(TicketPrice.amount_minor == 14000))
    price.amount_minor = 14500
    session.flush()
    seed_module.seed()
    session.expire_all()
    assert session.get(TicketPrice, price.id).amount_minor == 14500
