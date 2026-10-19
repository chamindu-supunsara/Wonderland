"""Apply mock Admission facts from SQS without accessing Admission's database."""

import argparse
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from wonderland_events.health import heartbeat
from wonderland_events.transport import aws_client, consume_one

from analytics_app.cloud_health import poll_heartbeat
from analytics_app.mock_pipeline import apply_fact


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    admission_queue_url: str
    aws_region: str = "ap-south-1"
    mock_analytics_enabled: bool = False


def apply_admission(session, event):
    if event.source != "admission":
        raise ValueError("Unexpected admission source")
    return apply_fact(
        session,
        dict(
            id=event.event_id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            payload=event.data,
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.mock_analytics_enabled:
        raise SystemExit("Explicit mock analytics mode required")
    factory = sessionmaker(
        create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=2,
            connect_args={"connect_timeout": 5},
        )
    )
    client = aws_client("sqs", settings.aws_region)
    while True:
        messages = consume_one(
            factory,
            "analytics",
            "analytics-admissions-v1",
            settings.admission_queue_url,
            client,
            apply_admission,
            wait=0 if args.once else 20,
        )
        poll_heartbeat(factory, "analytics-admissions", messages)
        heartbeat()
        if args.once:
            return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
