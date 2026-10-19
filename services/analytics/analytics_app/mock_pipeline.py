"""Local at-least-once mock event delivery; source acknowledgement follows Analytics commit."""

import argparse
import hashlib
import json
import logging
import time
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    database_url: str
    admission_feed_database_url: str
    mock_analytics_enabled: bool = False


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    admission_id: UUID
    ticket_id: UUID
    booking_id: UUID
    guest_number: int = Field(strict=True, ge=1, le=5)
    tier_code: Literal["INDIVIDUAL", "COUPLE", "FAMILY", "GROUP"]
    mode: Literal["MOCK"]
    occurred_at: AwareDatetime
    recorded_at: AwareDatetime
    ride_id: UUID | None = None
    attraction_id: UUID | None = None
    attraction_name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=40)

    @model_validator(mode="after")
    def complete_ride(self):
        fields = (self.ride_id, self.attraction_id, self.attraction_name, self.category)
        if any(value is not None for value in fields) and not all(
            value is not None for value in fields
        ):
            raise ValueError("Incomplete ride fact")
        return self


def apply_fact(session, row):
    fact = Fact.model_validate(row["payload"])
    kind = row["event_type"]
    if row["aggregate_id"] != fact.admission_id or kind not in {
        "MockGuestCheckedIn",
        "MockRideUsed",
    }:
        raise ValueError("Invalid mock event identity/type")
    if (kind == "MockRideUsed") != (fact.ride_id is not None):
        raise ValueError("Wrong fact shape")
    if kind == "MockGuestCheckedIn" and row["aggregate_version"] != 1:
        raise ValueError("Entry must be aggregate version one")
    if kind == "MockRideUsed" and row["aggregate_version"] < 2:
        raise ValueError("Ride must follow the entry event version")
    canonical = {
        "type": kind,
        "aggregate_id": str(row["aggregate_id"]),
        "version": row["aggregate_version"],
        "payload": fact.model_dump(mode="json"),
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    inserted = session.execute(
        text("""INSERT INTO analytics.mock_events
          (event_id,payload_hash,admission_id,aggregate_version,event_type)
          VALUES(:id,:hash,:admission,:version,:kind)
          ON CONFLICT(event_id) DO NOTHING RETURNING event_id"""),
        dict(
            id=row["id"],
            hash=digest,
            admission=fact.admission_id,
            version=row["aggregate_version"],
            kind=kind,
        ),
    ).scalar()
    if inserted is None:
        if (
            session.scalar(
                text("SELECT payload_hash FROM analytics.mock_events WHERE event_id=:id"),
                {"id": row["id"]},
            )
            != digest
        ):
            raise ValueError("Event ID reused with different content")
        return False
    values = dict(
        event=row["id"],
        admission=fact.admission_id,
        occurred=fact.occurred_at,
        recorded=fact.recorded_at,
    )
    if kind == "MockGuestCheckedIn":
        session.execute(
            text("""INSERT INTO analytics.mock_arrivals
          (admission_id,event_id,ticket_id,tier_code,occurred_at,recorded_at)
          VALUES(:admission,:event,:ticket,:tier,:occurred,:recorded)"""),
            {**values, "ticket": fact.ticket_id, "tier": fact.tier_code},
        )
    else:
        session.execute(
            text("""INSERT INTO analytics.mock_rides
          (ride_id,event_id,admission_id,attraction_id,attraction_name,category,occurred_at,recorded_at)
          VALUES(:ride,:event,:admission,:attraction,:name,:category,:occurred,:recorded)"""),
            {
                **values,
                "ride": fact.ride_id,
                "attraction": fact.attraction_id,
                "name": fact.attraction_name,
                "category": fact.category,
            },
        )
    return True


def deliver_batch(source_factory, target_factory, limit=100):
    with source_factory() as source:
        rows = (
            source.execute(
                text(
                    "SELECT * FROM admission.mock_analytics_feed "
                    "ORDER BY created_at,id LIMIT :limit"
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
    delivered = 0
    errors = 0
    for row in rows:
        try:
            with target_factory.begin() as target:
                apply_fact(target, row)
            # Crash before source receipt causes replay, suppressed by the committed event hash.
            with source_factory.begin() as source:
                source.execute(
                    text(
                        "INSERT INTO admission.mock_analytics_receipts(event_id) "
                        "VALUES(:id) ON CONFLICT DO NOTHING"
                    ),
                    {"id": row["id"]},
                )
            delivered += 1
        except Exception as exc:
            errors += 1
            log.error("mock event retained event=%s error=%s", row["id"], type(exc).__name__)
    with source_factory() as source:
        pending = (
            source.execute(
                text(
                    "SELECT count(*) AS total,min(created_at) AS oldest "
                    "FROM admission.mock_analytics_feed"
                )
            )
            .mappings()
            .one()
        )
    with target_factory.begin() as target:
        target.execute(
            text("""INSERT INTO analytics.mock_pipeline_state
          (id,polled_at,pending_events,retained_errors,oldest_pending_recorded_at)
          VALUES(1,now(),:pending,:errors,:oldest) ON CONFLICT(id) DO UPDATE
          SET polled_at=EXCLUDED.polled_at,pending_events=EXCLUDED.pending_events,
          retained_errors=EXCLUDED.retained_errors,oldest_pending_recorded_at=EXCLUDED.oldest_pending_recorded_at"""),
            {"pending": pending["total"], "errors": errors, "oldest": pending["oldest"]},
        )
    return delivered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.mock_analytics_enabled:
        raise SystemExit("Explicit MOCK_ANALYTICS_ENABLED=true is required")
    factories = [
        sessionmaker(create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5}))
        for url in [settings.admission_feed_database_url, settings.database_url]
    ]
    while True:
        try:
            count = deliver_batch(*factories)
            if count:
                log.info("mock delivery batch acknowledged=%s", count)
        except Exception as exc:
            log.error("mock pipeline unavailable error=%s", type(exc).__name__)
        if args.once:
            return
        time.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
