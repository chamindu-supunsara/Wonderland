"""Initial Booking tables, frozen independently of future ORM model changes."""
from alembic import op

revision = "booking_0001"
down_revision = None


def upgrade():
    op.execute("""
    CREATE TABLE booking.visit_slots (
      id UUID PRIMARY KEY, visit_date DATE NOT NULL, starts_at TIMESTAMPTZ NOT NULL,
      ends_at TIMESTAMPTZ NOT NULL, capacity_guests INTEGER NOT NULL,
      held_guests INTEGER NOT NULL DEFAULT 0, confirmed_guests INTEGER NOT NULL DEFAULT 0,
      UNIQUE (visit_date, starts_at), CHECK (ends_at > starts_at),
      CHECK (capacity_guests > 0 AND held_guests >= 0 AND confirmed_guests >= 0),
      CHECK (held_guests + confirmed_guests <= capacity_guests)
    );
    CREATE INDEX ix_booking_visit_slots_visit_date ON booking.visit_slots(visit_date);
    CREATE TABLE booking.bookings (
      id UUID PRIMARY KEY, reference VARCHAR(40) NOT NULL UNIQUE,
      user_sub VARCHAR(128) NOT NULL, idempotency_key UUID NOT NULL,
      request_hash VARCHAR(64) NOT NULL, slot_id UUID NOT NULL REFERENCES booking.visit_slots(id),
      visit_date DATE NOT NULL, starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
      tier_id UUID NOT NULL, tier_code VARCHAR(20) NOT NULL, tier_name VARCHAR(80) NOT NULL,
      guest_count INTEGER NOT NULL, amount_minor INTEGER NOT NULL, currency VARCHAR(3) NOT NULL,
      price_version INTEGER NOT NULL, status VARCHAR(30) NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (user_sub,idempotency_key),
      CHECK (guest_count BETWEEN 1 AND 5 AND amount_minor > 0 AND price_version > 0),
      CHECK (status IN ('PENDING_PAYMENT','CANCELLED','EXPIRED'))
    );
    CREATE INDEX ix_booking_bookings_user_sub ON booking.bookings(user_sub);
    CREATE INDEX ix_booking_bookings_slot_id ON booking.bookings(slot_id);
    CREATE INDEX ix_booking_bookings_expires_at ON booking.bookings(expires_at);
    CREATE TABLE booking.outbox_events (
      id UUID PRIMARY KEY, booking_id UUID NOT NULL REFERENCES booking.bookings(id),
      event_type VARCHAR(60) NOT NULL, payload JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_booking_outbox_events_booking_id ON booking.outbox_events(booking_id);
    """)


def downgrade():
    op.execute("DROP TABLE booking.outbox_events, booking.bookings, booking.visit_slots")
