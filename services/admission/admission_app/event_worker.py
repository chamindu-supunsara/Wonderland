"""Publish Admission's transactional outbox to its environment-specific SNS topic."""

import argparse
import logging
import time

from wonderland_events.health import heartbeat
from wonderland_events.transport import aws_client, counts, publish_one, requeue_failed

from admission_app.config import get_settings
from admission_app.db import session_factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publish", "status", "requeue"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--event-id")
    args = parser.parse_args()
    factory = session_factory()
    if args.action == "status":
        print(counts(factory, "admission"))
        return
    if args.action == "requeue":
        print("Requeued:", requeue_failed(factory, "admission", args.event_id))
        return
    settings = get_settings()
    if not settings.mock_admission_enabled or not settings.events_topic_arn:
        raise SystemExit("Explicit mock mode and EVENTS_TOPIC_ARN are required")
    client = aws_client("sns", settings.cognito_region)
    while True:
        processed = publish_one(factory, "admission", settings.events_topic_arn, client)
        heartbeat()
        if args.once:
            return
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
