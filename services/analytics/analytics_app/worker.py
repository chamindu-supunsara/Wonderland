"""Durable lifecycle projection and explicitly simulated purchase facts."""

import argparse
import json
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from wonderland_events.health import heartbeat
from wonderland_events.transport import aws_client, consume_one

from analytics_app.cloud_health import poll_heartbeat


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    booking_queue_url: str = ""
    aws_region: str = "ap-south-1"


def apply_booking(session, event):
    if event.source != "booking" or event.event_type not in {
        "BookingPaymentRequested",
        "BookingCancelled",
        "BookingExpired",
        "MockBookingConfirmed",
        "MockBookingPaymentFailed",
    }:
        raise ValueError("Unexpected booking event")
    expected = {
        "BookingPaymentRequested": "PENDING_PAYMENT",
        "BookingCancelled": "CANCELLED",
        "BookingExpired": "EXPIRED",
        "MockBookingConfirmed": "CONFIRMED",
        "MockBookingPaymentFailed": "PAYMENT_FAILED",
    }[event.event_type]
    if event.event_type.startswith("Mock") and event.data.get("payment_mode") != "MOCK":
        raise ValueError("Mock confirmations must be labelled MOCK")
    if (
        event.data.get("id") != str(event.aggregate_id)
        or event.data.get("status") != expected
        or type(event.data.get("guest_count")) is not int
        or not 1 <= event.data["guest_count"] <= 5
        or type(event.data.get("amount_minor")) is not int
        or event.data["amount_minor"] <= 0
    ):
        raise ValueError("Invalid booking snapshot")
    session.execute(
        text("""
        INSERT INTO analytics.booking_projection(booking_id,version,payload)
        VALUES(:id,:version,CAST(:payload AS jsonb))
        ON CONFLICT(booking_id) DO UPDATE SET version=EXCLUDED.version,payload=EXCLUDED.payload,
        received_at=now() WHERE booking_projection.version < EXCLUDED.version
    """),
        {
            "id": event.aggregate_id,
            "version": event.aggregate_version,
            "payload": json.dumps(event.data),
        },
    )
    if event.event_type == "MockBookingConfirmed":
        data = event.data
        if (
            data.get("tier_code") not in {"INDIVIDUAL", "COUPLE", "FAMILY", "GROUP"}
            or data.get("currency") != "USD"
        ):
            raise ValueError("Invalid mock purchase currency/tier")
        values = {
            "booking": event.aggregate_id,
            "event": event.event_id,
            "tier": data["tier_code"],
            "guests": data["guest_count"],
            "amount": data["amount_minor"],
            "currency": data["currency"],
            "confirmed": event.occurred_at,
        }
        session.execute(
            text("""INSERT INTO analytics.mock_purchases
          (booking_id,event_id,tier_code,guest_count,amount_minor,currency,confirmed_at)
          VALUES(:booking,:event,:tier,:guests,:amount,:currency,:confirmed)
          ON CONFLICT(booking_id) DO NOTHING"""),
            values,
        )
        existing = session.execute(
            text("""SELECT event_id,tier_code,guest_count,amount_minor,currency,confirmed_at
          FROM analytics.mock_purchases WHERE booking_id=:booking"""),
            values,
        ).one()
        if tuple(existing) != (
            event.event_id,
            data["tier_code"],
            data["guest_count"],
            data["amount_minor"],
            data["currency"],
            event.occurred_at,
        ):
            raise ValueError("Conflicting purchase confirmation for one booking")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    factory = sessionmaker(
        create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
            pool_size=2,
            max_overflow=2,
        )
    )
    if args.status:
        with factory() as session:
            print("Inbox:", session.scalar(text("SELECT count(*) FROM analytics.event_inbox")))
            print(
                "Bookings:",
                session.scalar(text("SELECT count(*) FROM analytics.booking_projection")),
            )
        return
    if not settings.booking_queue_url:
        raise SystemExit("BOOKING_QUEUE_URL is required")
    client = aws_client("sqs", settings.aws_region)
    while True:
        messages = consume_one(
            factory,
            "analytics",
            "analytics-bookings-v1",
            settings.booking_queue_url,
            client,
            apply_booking,
            wait=0 if args.once else 20,
        )
        poll_heartbeat(factory, "analytics-bookings", messages)
        heartbeat()
        if args.once:
            return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
