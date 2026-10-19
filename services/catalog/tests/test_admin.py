from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Principal, current_user
from app.main import create_app
from app.models import Attraction, CatalogAudit, CatalogOutbox, TicketPrice, TicketTier

ADMIN = Principal(user_id="admin-sub", username="admin", role="administrator")
VISITOR = Principal(user_id="visitor-sub", username="visitor", role="visitor")
PAYLOAD = {
    "name": "Test Discovery Ride",
    "description": "Discover a world of play.",
    "category": "INTERACTIVE",
    "thrill_level": "LOW",
    "min_age": None,
    "min_height_cm": 90,
    "guidance_text": "Follow staff instructions.",
}


@pytest.fixture
def admin_client(client):
    client.app.dependency_overrides[current_user] = lambda: ADMIN
    return client


def test_attraction_create_edit_retire_preserves_record_and_audit(admin_client, session):
    created = admin_client.post("/api/v1/admin/attractions", json=PAYLOAD)
    assert created.status_code == 201
    ride = created.json()
    assert ride["revision"] == 1 and ride["status"] == "ACTIVE"
    edited = admin_client.put(
        f"/api/v1/admin/attractions/{ride['id']}",
        json={
            **PAYLOAD,
            "name": "Updated Ride",
            "expected_revision": 1,
        },
    )
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    assert admin_client.get(f"/api/v1/attractions/{ride['id']}").json()["name"] == "Updated Ride"
    retired = admin_client.post(
        f"/api/v1/admin/attractions/{ride['id']}/retire",
        json={
            "expected_revision": 2,
        },
    )
    assert retired.status_code == 200 and retired.json()["revision"] == 3
    assert admin_client.get(f"/api/v1/attractions/{ride['id']}").status_code == 404
    assert len(admin_client.get("/api/v1/admin/attractions?status=RETIRED").json()) == 1
    assert session.scalar(select(func.count()).select_from(Attraction)) == 1
    events = admin_client.get(f"/api/v1/admin/audit?resource_id={ride['id']}").json()
    assert {event["action"] for event in events} == {
        "ATTRACTION_CREATED",
        "ATTRACTION_UPDATED",
        "ATTRACTION_RETIRED",
    }
    assert all(event["actor_id"] == ADMIN.user_id for event in events)


def test_stale_edit_and_retirement_cannot_overwrite_newer_revision(admin_client):
    ride = admin_client.post("/api/v1/admin/attractions", json=PAYLOAD).json()
    url = f"/api/v1/admin/attractions/{ride['id']}"
    assert admin_client.put(url, json={**PAYLOAD, "expected_revision": 1}).status_code == 200
    assert admin_client.put(url, json={**PAYLOAD, "expected_revision": 1}).status_code == 409
    assert admin_client.post(f"{url}/retire", json={"expected_revision": 1}).status_code == 409
    assert admin_client.get(f"/api/v1/attractions/{ride['id']}").status_code == 200


def test_retired_records_are_read_only_and_repeat_retire_has_no_duplicate_audit(admin_client):
    ride = admin_client.post("/api/v1/admin/attractions", json=PAYLOAD).json()
    url = f"/api/v1/admin/attractions/{ride['id']}"
    admin_client.post(f"{url}/retire", json={"expected_revision": 1})
    assert admin_client.put(url, json={**PAYLOAD, "expected_revision": 2}).status_code == 409
    assert admin_client.post(f"{url}/retire", json={"expected_revision": 2}).status_code == 200
    assert len(admin_client.get("/api/v1/admin/audit").json()) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"name": "   "},
        {"description": ""},
        {"guidance_text": " "},
        {"category": "UNKNOWN"},
        {"thrill_level": "EXTREME"},
        {"min_age": -1},
        {"min_height_cm": 301},
        {"min_age": 1.5},
        {"min_age": True},
        {"status": "RETIRED"},
    ],
)
def test_invalid_attractions_rejected_without_writes(admin_client, session, change):
    assert (
        admin_client.post("/api/v1/admin/attractions", json={**PAYLOAD, **change}).status_code
        == 422
    )
    assert session.scalar(select(func.count()).select_from(Attraction)) == 0
    assert session.scalar(select(func.count()).select_from(CatalogAudit)) == 0


def seed_tier(session):
    tier = TicketTier(code="INDIVIDUAL", name="Individual", min_guests=1, max_guests=1)
    session.add(tier)
    session.flush()
    session.add(TicketPrice(tier_id=tier.id, amount_minor=4000, currency="USD", version=1))
    session.commit()
    return tier.id


def test_price_publication_preserves_history_and_changes_public_catalog(admin_client, session):
    tier_id = seed_tier(session)
    result = admin_client.post(
        f"/api/v1/admin/ticket-tiers/{tier_id}/prices",
        json={
            "amount_minor": 4250,
            "expected_version": 1,
        },
    )
    assert result.status_code == 201
    assert result.json()["version"] == 2 and result.json()["created_by"] == ADMIN.user_id
    history = admin_client.get(f"/api/v1/admin/ticket-tiers/{tier_id}/prices").json()
    assert [(p["amount_minor"], p["active"]) for p in history] == [(4250, True), (4000, False)]
    public = admin_client.get("/api/v1/ticket-tiers").json()[0]
    assert public["amount_minor"] == 4250 and public["price_version"] == 2
    assert admin_client.get("/api/v1/admin/audit").json()[0]["action"] == "PRICE_PUBLISHED"
    emitted = session.scalar(select(CatalogOutbox).where(CatalogOutbox.aggregate_id == tier_id))
    assert emitted.aggregate_version == 2 and emitted.payload["amount_minor"] == 4250


def test_price_conflicts_do_not_corrupt_active_price(admin_client, session):
    tier_id = seed_tier(session)
    url = f"/api/v1/admin/ticket-tiers/{tier_id}/prices"
    assert (
        admin_client.post(url, json={"amount_minor": 4000, "expected_version": 1}).status_code
        == 409
    )
    assert (
        admin_client.post(url, json={"amount_minor": 4200, "expected_version": 1}).status_code
        == 201
    )
    assert (
        admin_client.post(url, json={"amount_minor": 4300, "expected_version": 1}).status_code
        == 409
    )
    assert len(admin_client.get(url).json()) == 2


@pytest.mark.parametrize("amount", [0, -1, 1.5, "4250", True, 100000001])
def test_invalid_price_rejected(admin_client, session, amount):
    tier_id = seed_tier(session)
    response = admin_client.post(
        f"/api/v1/admin/ticket-tiers/{tier_id}/prices",
        json={
            "amount_minor": amount,
            "expected_version": 1,
        },
    )
    assert response.status_code == 422
    assert len(admin_client.get(f"/api/v1/admin/ticket-tiers/{tier_id}/prices").json()) == 1


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/attractions", None),
        ("POST", "/attractions", PAYLOAD),
        ("PUT", f"/attractions/{uuid4()}", {**PAYLOAD, "expected_revision": 1}),
        ("POST", f"/attractions/{uuid4()}/retire", {"expected_revision": 1}),
        ("GET", "/ticket-tiers", None),
        ("GET", f"/ticket-tiers/{uuid4()}/prices", None),
        ("POST", f"/ticket-tiers/{uuid4()}/prices", {"amount_minor": 4250, "expected_version": 1}),
        ("GET", "/audit", None),
    ],
)
def test_every_admin_operation_rejects_anonymous_and_visitor(client, method, path, body):
    url = f"/api/v1/admin{path}"
    assert client.request(method, url, json=body).status_code == 401
    client.app.dependency_overrides[current_user] = lambda: VISITOR
    assert client.request(method, url, json=body).status_code == 403


def test_missing_resources_and_invalid_filters(admin_client):
    missing = uuid4()
    assert (
        admin_client.put(
            f"/api/v1/admin/attractions/{missing}",
            json={
                **PAYLOAD,
                "expected_revision": 1,
            },
        ).status_code
        == 404
    )
    assert admin_client.get(f"/api/v1/admin/ticket-tiers/{missing}/prices").status_code == 404
    assert admin_client.get("/api/v1/admin/attractions?status=BOGUS").status_code == 422
    assert admin_client.get("/api/v1/admin/audit?limit=1000").status_code == 422


def test_failed_audit_rolls_back_price_publication(admin_client, session, monkeypatch):
    from app.api import admin

    tier_id = seed_tier(session)

    def fail(*args):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(admin, "audit", fail)
    with pytest.raises(RuntimeError, match="Simulated audit failure"):
        admin_client.post(
            f"/api/v1/admin/ticket-tiers/{tier_id}/prices",
            json={
                "amount_minor": 4250,
                "expected_version": 1,
            },
        )
    history = admin_client.get(f"/api/v1/admin/ticket-tiers/{tier_id}/prices").json()
    assert len(history) == 1 and history[0]["active"] is True


def test_seed_does_not_recreate_renamed_or_retired_attraction(session, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app import seed

    monkeypatch.setattr(
        seed,
        "session_factory",
        lambda: sessionmaker(bind=session.connection(), join_transaction_mode="create_savepoint"),
    )
    seed.seed()
    ride = session.scalar(select(Attraction).where(Attraction.seed_key == "skyline-rush"))
    ride.name = "Administrator renamed ride"
    ride.status = "RETIRED"
    session.flush()
    seed.seed()
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(Attraction)) == 4
    assert session.get(Attraction, ride.id).status == "RETIRED"
    assert session.get(Attraction, ride.id).name == "Administrator renamed ride"


def test_concurrent_price_writers_create_only_one_successor(engine):
    """Use committed disposable rows so independent test connections contend for a lock."""
    tier_id = uuid4()
    with Session(engine) as session, session.begin():
        session.add(
            TicketTier(
                id=tier_id,
                code=f"TEST_{uuid4().hex[:12]}",
                name="Race test",
                min_guests=1,
                max_guests=1,
            )
        )
        session.flush()
        session.add(TicketPrice(tier_id=tier_id, amount_minor=4000, version=1))
    try:
        start = Barrier(2)

        def publish(amount):
            app = create_app()
            app.dependency_overrides[current_user] = lambda: ADMIN
            with TestClient(app) as client:
                start.wait(timeout=10)
                return client.post(
                    f"/api/v1/admin/ticket-tiers/{tier_id}/prices",
                    json={
                        "amount_minor": amount,
                        "expected_version": 1,
                    },
                ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(publish, [4250, 4500]))
        assert sorted(statuses) == [201, 409]
        with Session(engine) as session:
            prices = session.scalars(
                select(TicketPrice).where(TicketPrice.tier_id == tier_id)
            ).all()
            assert len(prices) == 2
            assert sum(price.active for price in prices) == 1
    finally:
        with Session(engine) as session, session.begin():
            for cls, column in [
                (CatalogOutbox, CatalogOutbox.aggregate_id),
                (CatalogAudit, CatalogAudit.resource_id),
                (TicketPrice, TicketPrice.tier_id),
                (TicketTier, TicketTier.id),
            ]:
                from sqlalchemy import delete

                session.execute(delete(cls).where(column == tier_id))
