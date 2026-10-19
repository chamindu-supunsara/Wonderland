"""Durable delivery metadata, aggregate sequence, pricing inbox/projection."""
from alembic import op
revision = "booking_0002"
down_revision = "booking_0001"

def upgrade():
    op.execute("""
        ALTER TABLE booking.bookings ADD COLUMN event_version INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE booking.outbox_events
          ADD COLUMN aggregate_id UUID,
          ADD COLUMN aggregate_version INTEGER,
          ADD COLUMN published_at TIMESTAMPTZ,
          ADD COLUMN sns_message_id VARCHAR(100),
          ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          ADD COLUMN failed_at TIMESTAMPTZ,
          ADD COLUMN last_error VARCHAR(120);
        WITH numbered AS (
          SELECT id, row_number() OVER(PARTITION BY booking_id ORDER BY created_at,id) AS n
          FROM booking.outbox_events
        )
        UPDATE booking.outbox_events e SET aggregate_id=booking_id,aggregate_version=n.n
          FROM numbered n WHERE n.id=e.id;
        ALTER TABLE booking.outbox_events ALTER COLUMN aggregate_id SET NOT NULL,
          ALTER COLUMN aggregate_version SET NOT NULL,
          ADD CHECK (attempts >= 0 AND aggregate_version > 0);
        UPDATE booking.bookings b SET event_version=COALESCE(
          (SELECT max(aggregate_version) FROM booking.outbox_events e WHERE e.booking_id=b.id),0);
        CREATE INDEX ix_booking_outbox_pending ON booking.outbox_events(next_attempt_at,created_at)
          WHERE published_at IS NULL AND failed_at IS NULL;
        CREATE TABLE booking.event_inbox (
          consumer VARCHAR(80) NOT NULL, event_id UUID NOT NULL, payload_hash VARCHAR(64) NOT NULL,
          received_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(consumer,event_id)
        );
        CREATE TABLE booking.ticket_price_projection (
          tier_id UUID PRIMARY KEY, version INTEGER NOT NULL CHECK(version > 0),
          payload JSONB NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

def downgrade():
    op.execute("""
        DROP TABLE booking.ticket_price_projection, booking.event_inbox;
        DROP INDEX booking.ix_booking_outbox_pending;
        ALTER TABLE booking.outbox_events DROP COLUMN aggregate_id,
          DROP COLUMN aggregate_version, DROP COLUMN published_at, DROP COLUMN sns_message_id,
          DROP COLUMN attempts, DROP COLUMN next_attempt_at, DROP COLUMN failed_at,
          DROP COLUMN last_error;
        ALTER TABLE booking.bookings DROP COLUMN event_version;
    """)

