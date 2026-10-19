"""Independent mock ticket projection, guest entries, ride facts and outbox."""
from alembic import op

revision = "admission_0001"
down_revision = None


def upgrade():
    op.execute("""
      CREATE TABLE admission.ticket_projection (
        id UUID PRIMARY KEY, reference VARCHAR(45) NOT NULL UNIQUE,
        booking_id UUID NOT NULL, booking_reference VARCHAR(40) NOT NULL,
        user_sub VARCHAR(128) NOT NULL, guest_number INTEGER NOT NULL CHECK(guest_number BETWEEN 1 AND 5),
        tier_code VARCHAR(20) NOT NULL, tier_name VARCHAR(80) NOT NULL,
        starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL CHECK(ends_at>starts_at)
      );
      CREATE INDEX ix_admission_ticket_owner ON admission.ticket_projection(user_sub);
      CREATE INDEX ix_admission_ticket_booking ON admission.ticket_projection(booking_id);
      CREATE TABLE admission.check_ins (
        id UUID PRIMARY KEY, ticket_id UUID NOT NULL UNIQUE REFERENCES admission.ticket_projection(id),
        actor_sub VARCHAR(128) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(), event_version INTEGER NOT NULL CHECK(event_version>0)
      );
      CREATE TABLE admission.ride_uses (
        id UUID PRIMARY KEY, admission_id UUID NOT NULL REFERENCES admission.check_ins(id),
        attraction_id UUID NOT NULL, attraction_name VARCHAR(120) NOT NULL, category VARCHAR(40) NOT NULL,
        actor_sub VARCHAR(128) NOT NULL, idempotency_key UUID NOT NULL, request_hash VARCHAR(64) NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL, recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(actor_sub,idempotency_key)
      );
      CREATE INDEX ix_admission_rides_visit ON admission.ride_uses(admission_id);
      CREATE TABLE admission.outbox_events (
        id UUID PRIMARY KEY, aggregate_id UUID NOT NULL REFERENCES admission.check_ins(id),
        aggregate_version INTEGER NOT NULL CHECK(aggregate_version>0), event_type VARCHAR(60) NOT NULL,
        payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        published_at TIMESTAMPTZ, sns_message_id VARCHAR(100), attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(), failed_at TIMESTAMPTZ, last_error VARCHAR(120),
        UNIQUE(aggregate_id,aggregate_version)
      );
      CREATE INDEX ix_admission_outbox_pending ON admission.outbox_events(next_attempt_at)
      WHERE published_at IS NULL AND failed_at IS NULL;
    """)


def downgrade():
    op.execute("DROP TABLE admission.outbox_events, admission.ride_uses, admission.check_ins, admission.ticket_projection")
