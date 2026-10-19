import argparse
import logging
import time

from wonderland_events.health import heartbeat
from wonderland_events.transport import (
    aws_client,
    consume_one,
    counts,
    publish_one,
    requeue_failed,
)

from booking_app.config import get_settings
from booking_app.db import session_factory
from booking_app.pricing_projection import apply_price


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publish", "consume-prices", "status", "requeue"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--event-id")
    args = parser.parse_args()
    settings = get_settings()
    factory = session_factory()
    if args.action == "status":
        print(counts(factory, "booking"))
        return
    if args.action == "requeue":
        print("Requeued:", requeue_failed(factory, "booking", args.event_id))
        return
    publishing = args.action == "publish"
    target = settings.events_topic_arn if publishing else settings.pricing_queue_url
    if not target:
        raise SystemExit("Configure EVENTS_TOPIC_ARN / PRICING_QUEUE_URL for this worker")
    client = aws_client("sns" if publishing else "sqs", settings.cognito_region)
    while True:
        if publishing:
            processed = publish_one(factory, "booking", target, client)
        else:
            processed = consume_one(
                factory,
                "booking",
                "booking-prices-v1",
                target,
                client,
                apply_price,
                wait=0 if args.once else 20,
            )
        heartbeat()
        if args.once:
            return
        if publishing and not processed:
            time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
