"""Successful SQS-poll freshness; not a claim that every received event applied."""

from sqlalchemy import text


def poll_heartbeat(factory, worker, messages):
    with factory.begin() as session:
        session.execute(
            text("""INSERT INTO analytics.cloud_worker_state
          (worker_name,last_polled_at,last_batch_messages) VALUES(:worker,now(),:messages)
          ON CONFLICT(worker_name) DO UPDATE SET last_polled_at=EXCLUDED.last_polled_at,
          last_batch_messages=EXCLUDED.last_batch_messages"""),
            {"worker": worker, "messages": messages},
        )
