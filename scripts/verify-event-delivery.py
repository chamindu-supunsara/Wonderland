"""Bounded real-AWS smoke check. Publishes retained local events; never purges queues."""

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config as AwsConfig
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
for folder in ["packages/common", "services/catalog", "services/booking", "services/analytics"]:
    sys.path.insert(0, str(ROOT / folder))

from analytics_app.worker import apply_booking  # noqa: E402
from wonderland_events.transport import Event, consume_one, counts, publish_one  # noqa: E402

from app.events import snapshot_current_prices  # noqa: E402
from booking_app.pricing_projection import apply_price  # noqa: E402


def factory(service):
    url = dotenv_values(ROOT / f"services/{service}/.env")["DATABASE_URL"]
    return sessionmaker(create_engine(url, connect_args={"connect_timeout": 5}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deployment-smoke",
        action="store_true",
        help="Use the deployment session for this bounded smoke test only",
    )
    args = parser.parse_args()
    os.environ["AWS_CONFIG_FILE"] = str(ROOT / ".local/aws/config")
    os.environ["AWS_LOGIN_CACHE_DIRECTORY"] = str(ROOT / ".local/aws/login/cache")
    outputs = json.loads((ROOT / ".local/events.json").read_text(encoding="utf-8-sig"))
    factories = {service: factory(service) for service in ["catalog", "booking", "analytics"]}

    def client(service, role):
        profile = "wonderland-dev" if args.deployment_smoke else f"wonderland-{role}"
        return boto3.Session(profile_name=profile, region_name="ap-south-1").client(
            service,
            config=AwsConfig(
                connect_timeout=3, read_timeout=25, retries={"max_attempts": 2, "mode": "standard"}
            ),
        )

    snapshot_current_prices(factories["catalog"])
    for source, topic in [("catalog", "CatalogTopicArn"), ("booking", "BookingTopicArn")]:
        sns = client("sns", f"{source}-publisher")
        for _ in range(100):
            if not publish_one(factories[source], source, outputs[topic], sns):
                break
        status = counts(factories[source], source)
        print(source, status)
        if status["pending"] or status["failed"]:
            raise SystemExit("Outbox not drained; inspect delivery error codes before retrying")

    consumers = [
        ("booking", "booking-consumer", "BookingPricesUrl", "booking-prices-v1", apply_price),
        (
            "analytics",
            "analytics-consumer",
            "AnalyticsBookingsUrl",
            "analytics-bookings-v1",
            apply_booking,
        ),
    ]
    for schema, role, key, name, apply in consumers:
        sqs = client("sqs", role)
        for _ in range(100):
            if not consume_one(factories[schema], schema, name, outputs[key], sqs, apply, wait=2):
                break
        with factories[schema]() as session:
            print(
                schema,
                "durable receipts:",
                session.scalar(text(f"SELECT count(*) FROM {schema}.event_inbox")),
            )

    # Redeliver the identical persisted price event to exercise inbox deduplication over AWS.
    with factories["catalog"]() as session:
        row = (
            session.execute(
                text("SELECT * FROM catalog.outbox_events ORDER BY created_at DESC,id DESC LIMIT 1")
            )
            .mappings()
            .one()
        )
        duplicate = Event(
            event_id=row["id"],
            source="catalog",
            event_type=row["event_type"],
            aggregate_id=row["aggregate_id"],
            aggregate_version=row["aggregate_version"],
            occurred_at=row["created_at"],
            data=row["payload"],
        )
    with factories["booking"]() as session:
        before = session.scalar(text("SELECT count(*) FROM booking.event_inbox"))
    client("sns", "catalog-publisher").publish(
        TopicArn=outputs["CatalogTopicArn"], Message=duplicate.model_dump_json()
    )
    received = consume_one(
        factories["booking"],
        "booking",
        "booking-prices-v1",
        outputs["BookingPricesUrl"],
        client("sqs", "booking-consumer"),
        apply_price,
        wait=10,
    )
    assert received == 1, "Duplicate delivery was not observed; rerun after SNS delivery catches up"
    with factories["booking"]() as session:
        assert session.scalar(text("SELECT count(*) FROM booking.event_inbox")) == before
    with factories["catalog"]() as source, factories["booking"]() as target:
        expected = dict(
            source.execute(
                text("SELECT tier_id,version FROM catalog.ticket_prices WHERE active=true")
            ).all()
        )
        actual = dict(
            target.execute(
                text("SELECT tier_id,version FROM booking.ticket_price_projection")
            ).all()
        )
        assert expected and all(actual.get(k) == v for k, v in expected.items())
    with factories["booking"]() as source, factories["analytics"]() as target:
        expected = dict(source.execute(text("SELECT id,event_version FROM booking.bookings")).all())
        actual = dict(
            target.execute(
                text("SELECT booking_id,version FROM analytics.booking_projection")
            ).all()
        )
        assert all(actual.get(k) == v for k, v in expected.items())
    print("PASS: AWS delivery, current projections and duplicate receipt verified.")


if __name__ == "__main__":
    main()
