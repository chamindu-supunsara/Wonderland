"""Exercise the cloud event handlers using isolated Postgres and in-memory SNS/SQS."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from analytics_app.admission_worker import apply_admission
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from wonderland_events.transport import consume_one, publish_one


def check_events(delivered):
    factories = {
        s: sessionmaker(create_engine(delivered[s], pool_size=2, max_overflow=0))
        for s in ["admission", "analytics"]
    }
    event_id, admission_id = uuid4(), uuid4()
    timestamp = datetime.now(UTC).isoformat()
    payload = dict(
        admission_id=str(admission_id),
        ticket_id=str(uuid4()),
        booking_id=str(uuid4()),
        user_sub="private-visitor-identity",
        guest_number=1,
        tier_code="INDIVIDUAL",
        mode="MOCK",
        occurred_at=timestamp,
        recorded_at=timestamp,
    )
    with factories["admission"].begin() as session:
        session.execute(
            text("""INSERT INTO admission.ticket_projection
          (id,reference,booking_id,booking_reference,user_sub,guest_number,
           tier_code,tier_name,starts_at,ends_at)
          VALUES(:ticket_id,'MOCK-TEST',:booking_id,'TEST','private-visitor-identity',
                 1,'INDIVIDUAL','Test',now(),now()+interval '1 hour')"""),
            payload,
        )
        session.execute(
            text("""INSERT INTO admission.check_ins
          (id,ticket_id,actor_sub,occurred_at,event_version)
          VALUES(:id,:ticket,'test-staff',now(),1)"""),
            dict(id=admission_id, ticket=payload["ticket_id"]),
        )
        session.execute(
            text("""INSERT INTO admission.outbox_events
          (id,aggregate_id,aggregate_version,event_type,payload)
          VALUES(:id,:aggregate,1,'MockGuestCheckedIn',CAST(:payload AS jsonb))"""),
            dict(id=event_id, aggregate=admission_id, payload=json.dumps(payload)),
        )

    class Topic:
        bodies = []
        fail = True

        def publish(self, **kwargs):
            self.bodies.append(kwargs["Message"])
            if self.fail:
                raise TimeoutError("Simulate accepted SNS publish followed by lost response")
            return {"MessageId": str(uuid4())}

    topic = Topic()
    assert publish_one(factories["admission"], "admission", "topic", topic)
    with factories["admission"].begin() as session:
        state = session.execute(
            text("SELECT published_at,attempts FROM admission.outbox_events WHERE id=:id"),
            dict(id=event_id),
        ).one()
        assert state == (None, 1)
        session.execute(
            text("UPDATE admission.outbox_events SET next_attempt_at=now() WHERE id=:id"),
            dict(id=event_id),
        )
    topic.fail = False
    assert publish_one(factories["admission"], "admission", "topic", topic)
    assert len(topic.bodies) == 2 and topic.bodies[0] == topic.bodies[1]
    assert "user_sub" not in json.loads(topic.bodies[0])["data"]

    class Queue:
        body = topic.bodies[0]
        deleted = 0

        def receive_message(self, **kwargs):
            return {"Messages": [{"Body": self.body, "ReceiptHandle": "test-receipt"}]}

        def delete_message(self, **kwargs):
            self.deleted += 1

    queue = Queue()
    for body in topic.bodies:
        queue.body = body
        consume_one(
            factories["analytics"],
            "analytics",
            "cloud-admission-test",
            "queue",
            queue,
            apply_admission,
            wait=0,
        )
    assert queue.deleted == 2
    with factories["analytics"]() as session:
        assert (
            session.scalar(
                text("SELECT count(*) FROM analytics.mock_arrivals WHERE admission_id=:id"),
                dict(id=admission_id),
            )
            == 1
        )
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM analytics.event_inbox "
                    "WHERE consumer='cloud-admission-test'"
                )
            )
            == 1
        )
    # Reusing an event ID with changed content must not be acknowledged.
    tampered = json.loads(topic.bodies[0])
    tampered["data"]["guest_number"] = 2
    queue.body = json.dumps(tampered)
    consume_one(
        factories["analytics"],
        "analytics",
        "cloud-admission-test",
        "queue",
        queue,
        apply_admission,
        wait=0,
    )
    assert queue.deleted == 2
    # A poison fact must roll back its inbox insertion and remain retryable/DLQ eligible.
    tampered["event_id"] = str(uuid4())
    tampered["data"]["mode"] = "LIVE"
    queue.body = json.dumps(tampered)
    consume_one(
        factories["analytics"],
        "analytics",
        "cloud-admission-test",
        "queue",
        queue,
        apply_admission,
        wait=0,
    )
    assert queue.deleted == 2
    with factories["analytics"]() as session:
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM analytics.event_inbox "
                    "WHERE consumer='cloud-admission-test'"
                )
            )
            == 1
        )
    for factory in factories.values():
        factory.kw["bind"].dispose()
    return dict(
        retry_keeps_event_id=True,
        ambiguous_publish_duplicate_deduplicated=True,
        admission_user_identity_removed=True,
        tampering_retained=True,
        invalid_fact_rolls_back_inbox=True,
        cross_service_db_credentials_shared=False,
    )
