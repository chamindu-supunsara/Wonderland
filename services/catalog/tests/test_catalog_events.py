import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker
from wonderland_events.transport import Event, publish_one, requeue_failed

from app.events import price_event
from app.models import CatalogOutbox, TicketPrice, TicketTier


@pytest.fixture
def event_factory(session):
    return sessionmaker(bind=session.connection(), join_transaction_mode="create_savepoint")


@pytest.fixture
def price_outbox(session):
    # Other concurrency tests can leave committed events; isolate this publisher's due work.
    session.execute(text("UPDATE catalog.outbox_events SET next_attempt_at=now()+interval '1 day'"))
    tier = TicketTier(code="EVENT-TEST", name="Family", min_guests=1, max_guests=4)
    session.add(tier)
    session.flush()
    price = TicketPrice(tier_id=tier.id, amount_minor=14000, currency="USD", version=1)
    session.add(price)
    session.flush()
    price_event(session, tier, price)
    session.flush()
    return session.scalar(select(CatalogOutbox).where(CatalogOutbox.aggregate_id == tier.id))


class Topic:
    def __init__(self):
        self.sent = []
        self.fail = False

    def publish(self, **kwargs):
        self.sent.append(Event.model_validate_json(kwargs["Message"]))
        if self.fail:
            raise TimeoutError("unknown outcome")
        return {"MessageId": "sns-test"}


def test_sns_success_is_marked_and_not_sent_again(event_factory, session, price_outbox):
    topic = Topic()
    assert publish_one(event_factory, "catalog", "topic", topic)
    session.expire_all()
    assert price_outbox.published_at is not None and price_outbox.sns_message_id == "sns-test"
    assert not publish_one(event_factory, "catalog", "topic", topic)
    assert len(topic.sent) == 1


def test_sns_failure_retries_same_id_and_preserves_terminal_failure(
    event_factory, session, price_outbox
):
    topic = Topic()
    topic.fail = True
    for attempt in range(1, 11):
        session.execute(
            text("UPDATE catalog.outbox_events SET next_attempt_at=now() WHERE id=:id"),
            {"id": price_outbox.id},
        )
        session.flush()
        assert publish_one(event_factory, "catalog", "topic", topic)
        session.expire_all()
        assert price_outbox.attempts == attempt and price_outbox.published_at is None
    assert len({item.event_id for item in topic.sent}) == 1
    assert price_outbox.failed_at is not None
    assert not publish_one(event_factory, "catalog", "topic", topic)
    assert requeue_failed(event_factory, "catalog", str(price_outbox.id)) == 1
    topic.fail = False
    assert publish_one(event_factory, "catalog", "topic", topic)


def test_failed_outbox_insert_rolls_back_price_transaction(session):
    # Any failed event write aborts the shared DB transaction along with its domain writes.
    tier = TicketTier(code="ROLLBACK-TEST", name="Test", min_guests=1, max_guests=1)
    with pytest.raises(RuntimeError):
        with session.begin_nested():
            session.add(tier)
            session.flush()
            price_event(
                session,
                tier,
                TicketPrice(tier_id=tier.id, amount_minor=100, currency="USD", version=1),
            )
            session.flush()
            raise RuntimeError("simulate failure before commit")
    assert session.scalar(select(TicketTier).where(TicketTier.id == tier.id)) is None
    assert (
        session.scalar(select(CatalogOutbox).where(CatalogOutbox.aggregate_id == tier.id)) is None
    )
