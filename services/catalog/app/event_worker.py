import argparse
import logging
import time

from wonderland_events.health import heartbeat
from wonderland_events.transport import aws_client, counts, publish_one, requeue_failed

from app.config import get_settings
from app.db import session_factory
from app.events import snapshot_current_prices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publish", "snapshot", "status", "requeue"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--event-id")
    args = parser.parse_args()
    settings = get_settings()
    factory = session_factory()
    if args.action == "snapshot":
        snapshot_current_prices(factory)
        print("Current package snapshots queued transactionally.")
        return
    if args.action == "status":
        print(counts(factory, "catalog"))
        return
    if args.action == "requeue":
        print("Requeued:", requeue_failed(factory, "catalog", args.event_id))
        return
    if not settings.events_topic_arn:
        raise SystemExit("EVENTS_TOPIC_ARN is required")
    client = aws_client("sns", settings.cognito_region)
    while True:
        processed = publish_one(factory, "catalog", settings.events_topic_arn, client)
        heartbeat()
        if args.once:
            return
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
