"""At-least-once SNS publishing and commit-before-ack SQS consumption."""

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import boto3
from botocore.config import Config
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

log = logging.getLogger(__name__)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    schema_version: Literal[1] = 1
    event_type: str = Field(min_length=1, max_length=80)
    source: Literal["catalog", "booking", "admission"]
    aggregate_id: UUID
    aggregate_version: int = Field(strict=True, ge=1)
    occurred_at: datetime
    data: dict

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Event timestamps require a timezone")
        return value


def aws_client(service, region):
    # Default credential chain: temporary login/assumed-role profiles locally, workload roles later.
    return boto3.client(
        service,
        region_name=region,
        config=Config(
            connect_timeout=3,
            read_timeout=25 if service == "sqs" else 8,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def publish_one(factory, schema, topic, client):
    if schema not in {"catalog", "booking", "admission"}:
        raise ValueError("Unrecognized outbox")
    with factory.begin() as session:
        row = (
            session.execute(
                text(f"""
            SELECT * FROM {schema}.outbox_events
            WHERE published_at IS NULL AND failed_at IS NULL AND next_attempt_at <= now()
            ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED
        """)
            )
            .mappings()
            .first()
        )
        if row is None:
            return False
        try:
            envelope = Event(
                event_id=row["id"],
                source=schema,
                event_type=row["event_type"],
                aggregate_id=row["aggregate_id"],
                aggregate_version=row["aggregate_version"],
                occurred_at=row["created_at"],
                # Admission's analytical event contract excludes the visitor identity.
                data={
                    k: v
                    for k, v in row["payload"].items()
                    if schema != "admission" or k != "user_sub"
                },
            )
            result = client.publish(
                TopicArn=topic,
                Message=envelope.model_dump_json(),
                MessageAttributes={
                    "event_type": {"DataType": "String", "StringValue": envelope.event_type},
                    "source": {"DataType": "String", "StringValue": schema},
                },
            )
            session.execute(
                text(f"""
                UPDATE {schema}.outbox_events SET published_at=now(), sns_message_id=:message,
                attempts=attempts+1,last_error=NULL WHERE id=:id
            """),
                {"id": row["id"], "message": result["MessageId"]},
            )
            log.info("published event=%s type=%s", row["id"], row["event_type"])
        except Exception as exc:
            # SNS may have accepted a timed-out request. Keep the same event_id on every retry.
            attempts = row["attempts"] + 1
            code = type(exc).__name__
            if hasattr(exc, "response"):
                code = exc.response.get("Error", {}).get("Code", code)
            session.execute(
                text(f"""
                UPDATE {schema}.outbox_events SET attempts=:attempts,last_error=:error,
                next_attempt_at=:next,failed_at=:failed WHERE id=:id
            """),
                {
                    "id": row["id"],
                    "attempts": attempts,
                    "error": code[:120],
                    "next": datetime.now(UTC) + timedelta(seconds=min(300, 2 ** min(attempts, 9))),
                    "failed": datetime.now(UTC) if attempts >= 10 else None,
                },
            )
            log.warning("publish deferred event=%s error=%s attempt=%s", row["id"], code, attempts)
    return True


def consume_one(factory, schema, consumer, queue_url, client, apply, wait=20):
    if schema not in {"booking", "analytics"}:
        raise ValueError("Unrecognized inbox")
    messages = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait,
        VisibilityTimeout=60,
    ).get("Messages", [])
    for message in messages:
        try:
            body = message["Body"]
            if len(body.encode()) > 262144:
                raise ValueError("Oversize event")
            envelope = Event.model_validate_json(
                body
            )  # Raw SNS delivery, not a nested SNS wrapper.
            canonical = json.dumps(envelope.model_dump(mode="json"), sort_keys=True)
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            with factory.begin() as session:
                inserted = session.execute(
                    text(f"""
                    INSERT INTO {schema}.event_inbox(consumer,event_id,payload_hash)
                    VALUES(:consumer,:id,:hash) ON CONFLICT DO NOTHING RETURNING event_id
                """),
                    {"consumer": consumer, "id": envelope.event_id, "hash": digest},
                ).scalar()
                if inserted:
                    apply(session, envelope)
                else:
                    previous = session.execute(
                        text(f"""
                        SELECT payload_hash FROM {schema}.event_inbox
                        WHERE consumer=:consumer AND event_id=:id
                    """),
                        {"consumer": consumer, "id": envelope.event_id},
                    ).scalar_one()
                    if previous != digest:
                        raise ValueError("Event ID reused with a different payload")
            # A crash or delete failure here can deliver again; the committed inbox deduplicates it.
            client.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
            log.info(
                "consumed consumer=%s event=%s duplicate=%s",
                consumer,
                envelope.event_id,
                not bool(inserted),
            )
        except Exception as exc:
            # No acknowledgement: visibility timeout, retry, then processing DLQ.
            log.warning("message retained consumer=%s error=%s", consumer, type(exc).__name__)
    return len(messages)


def requeue_failed(factory, schema, event_id):
    if schema not in {"catalog", "booking", "admission"}:
        raise ValueError("Unrecognized outbox")
    with factory.begin() as session:
        return session.execute(
            text(f"""
            UPDATE {schema}.outbox_events SET failed_at=NULL,attempts=0,last_error=NULL,
            next_attempt_at=now() WHERE id=:id AND published_at IS NULL AND failed_at IS NOT NULL
        """),
            {"id": UUID(event_id)},
        ).rowcount


def counts(factory, schema):
    if schema not in {"catalog", "booking", "admission"}:
        raise ValueError("Unrecognized outbox")
    with factory() as session:
        return dict(
            session.execute(
                text(f"""
            SELECT count(*) FILTER(WHERE published_at IS NOT NULL) AS published,
            count(*) FILTER(WHERE published_at IS NULL AND failed_at IS NULL) AS pending,
            count(*) FILTER(WHERE failed_at IS NOT NULL) AS failed FROM {schema}.outbox_events
        """)
            )
            .mappings()
            .one()
        )
