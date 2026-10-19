from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from analytics_app.mock_pipeline import apply_fact
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytest_plugins = ["test_event_analytics"]


def event(admission=None, kind="MockGuestCheckedIn", version=1, **changes):
    admission = admission or uuid4()
    payload = dict(
        admission_id=str(admission),
        ticket_id=str(uuid4()),
        booking_id=str(uuid4()),
        guest_number=1,
        tier_code="FAMILY",
        mode="MOCK",
        occurred_at="2026-10-16T23:45:00Z",
        recorded_at=datetime.now(UTC).isoformat(),
        **changes,
    )
    if kind == "MockRideUsed":
        payload.update(
            ride_id=str(uuid4()),
            attraction_id=str(uuid4()),
            attraction_name="River Rapids",
            category="WATER",
        )
    return dict(
        id=uuid4(),
        aggregate_id=admission,
        aggregate_version=version,
        event_type=kind,
        payload=payload,
    )


def put(factory, row):
    with factory.begin() as session:
        return apply_fact(session, row)


def test_mock_fact_replay_and_hash_mismatch(analytics_factory):
    row = event()
    assert put(analytics_factory, row)
    assert not put(analytics_factory, row)
    changed = deepcopy(row)
    changed["payload"]["tier_code"] = "GROUP"
    with pytest.raises(ValueError, match="different content"):
        put(analytics_factory, changed)
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_arrivals")) == 1


def test_out_of_order_rides_and_colombo_date(analytics_factory):
    row = event()
    use = event(row["aggregate_id"], "MockRideUsed", 2)
    assert put(analytics_factory, use)
    with analytics_factory() as session:
        assert (
            session.scalar(
                text("SELECT rides_awaiting_arrival FROM reporting.mock_pipeline_health")
            )
            == 1
        )
    put(analytics_factory, row)
    with analytics_factory() as session:
        health = (
            session.execute(text("SELECT * FROM reporting.mock_pipeline_health")).mappings().one()
        )
        assert health["total_guest_arrivals"] == health["total_ride_uses"] == 1
        assert health["rides_awaiting_arrival"] == 0
        daily = (
            session.execute(text("SELECT * FROM reporting.mock_daily_arrivals")).mappings().one()
        )
        assert str(daily["visit_date"]) == "2026-10-17" and daily["guest_arrivals"] == 1
        hourly = (
            session.execute(text("SELECT * FROM reporting.mock_hourly_activity")).mappings().one()
        )
        assert hourly["hour_of_day"] == 5
        assert session.scalar(text("SELECT count(*) FROM reporting.mock_daily_hour_grid")) == 24
        assert (
            session.scalar(text("SELECT sum(guest_arrivals) FROM reporting.mock_daily_hour_grid"))
            == 1
        )


def test_people_not_package_or_ride_count(analytics_factory):
    a, b = event(), event()
    put(analytics_factory, a)
    put(analytics_factory, b)
    attraction = uuid4()
    for admission, version in [
        (a["aggregate_id"], 2),
        (a["aggregate_id"], 3),
        (b["aggregate_id"], 2),
    ]:
        use = event(admission, "MockRideUsed", version)
        use["payload"]["attraction_id"] = str(attraction)
        put(analytics_factory, use)
    with analytics_factory() as session:
        row = session.execute(
            text("SELECT ride_uses,unique_guests FROM reporting.mock_popular_rides")
        ).one()
        assert tuple(row) == (3, 2)
        assert (
            session.scalar(text("SELECT sum(guest_arrivals) FROM reporting.mock_daily_arrivals"))
            == 2
        )


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "REAL"},
        {"guest_number": True},
        {"occurred_at": "2026-10-17T10:00:00"},
        {"tier_code": "UNKNOWN"},
        {"user_sub": "private-owner"},
    ],
)
def test_invalid_nonmock_or_private_payload_rejected(analytics_factory, change):
    row = event()
    row["payload"].update(change)
    with pytest.raises(ValueError):
        put(analytics_factory, row)
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_events")) == 0


def test_different_event_cannot_duplicate_guest(analytics_factory):
    row = event()
    put(analytics_factory, row)
    other = deepcopy(row)
    other["id"] = uuid4()
    with pytest.raises(IntegrityError):
        put(analytics_factory, other)
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_arrivals")) == 1


def test_commit_before_source_ack_recovers_without_double_count(analytics_factory):
    from analytics_app.mock_pipeline import deliver_batch

    row = event()

    class Feed:
        acknowledged = False
        fail_ack = True

        def __call__(self):
            return self

        def begin(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params=None):
            sql = str(query)
            if sql.startswith("INSERT"):
                if self.fail_ack:
                    raise RuntimeError("lost acknowledgement")
                self.acknowledged = True
            return self

        def mappings(self):
            return self

        def all(self):
            return [] if self.acknowledged else [row]

        def one(self):
            return {"total": int(not self.acknowledged), "oldest": None}

    feed = Feed()
    assert deliver_batch(feed, analytics_factory) == 0
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_arrivals")) == 1
        assert session.scalar(text("SELECT retained_errors FROM reporting.mock_worker_health")) == 1
    feed.fail_ack = False
    assert deliver_batch(feed, analytics_factory) == 1
    assert deliver_batch(feed, analytics_factory) == 0
    with analytics_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM analytics.mock_arrivals")) == 1
        assert session.scalar(text("SELECT pending_events FROM reporting.mock_worker_health")) == 0


@pytest.mark.parametrize(
    "table", ["analytics.mock_arrivals", "admission.check_ins", "booking.bookings"]
)
def test_reporting_role_cannot_read_operational_or_identity_facts(analytics_factory, table):
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import DBAPIError

    with analytics_factory.kw["bind"].engine.begin() as connection:
        connection.execute(text("GRANT USAGE ON SCHEMA reporting TO metabase_reader_test"))
        connection.execute(
            text("GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO metabase_reader_test")
        )
    url = make_url(os.environ["DATABASE_URL"])
    assert url.database.endswith("_test")
    reader = create_engine(
        url.set(username="metabase_reader_test", password="metabase_reader_test_only")
    )
    try:
        with reader.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT total_guest_arrivals FROM reporting.mock_pipeline_health")
                )
                == 0
            )
            with pytest.raises(DBAPIError, match="permission denied"):
                connection.execute(text("SELECT * FROM " + table))
    finally:
        reader.dispose()
