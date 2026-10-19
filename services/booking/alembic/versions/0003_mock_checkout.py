"""Mock settlement receipts and guest demonstration tickets."""
from alembic import op
revision = "booking_0003"
down_revision = "booking_0002"

def upgrade():
    op.execute("""
      DO $$ DECLARE item record; BEGIN
        FOR item IN SELECT conname FROM pg_constraint
          WHERE conrelid='booking.bookings'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%status%'
        LOOP EXECUTE format('ALTER TABLE booking.bookings DROP CONSTRAINT %I',item.conname); END LOOP;
      END $$;
      ALTER TABLE booking.bookings ADD COLUMN payment_mode VARCHAR(12) NOT NULL DEFAULT 'NONE',
        ADD CHECK(status IN ('PENDING_PAYMENT','CANCELLED','EXPIRED','CONFIRMED','PAYMENT_FAILED')),
        ADD CHECK(payment_mode IN ('NONE','MOCK'));
      CREATE TABLE booking.mock_settlements (
        checkout_id UUID PRIMARY KEY, booking_id UUID NOT NULL UNIQUE REFERENCES booking.bookings(id),
        outcome VARCHAR(10) NOT NULL CHECK(outcome IN ('success','failure')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE TABLE booking.guest_tickets (
        id UUID PRIMARY KEY, booking_id UUID NOT NULL REFERENCES booking.bookings(id),
        guest_number INTEGER NOT NULL CHECK(guest_number BETWEEN 1 AND 5),
        reference VARCHAR(45) NOT NULL UNIQUE, issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(booking_id,guest_number)
      );
    """)

def downgrade():
    op.execute("""
      DO $$ BEGIN
        IF EXISTS(SELECT FROM booking.bookings WHERE status IN ('CONFIRMED','PAYMENT_FAILED'))
        THEN RAISE EXCEPTION 'Retained mock history prevents downgrade'; END IF;
      END $$;
      DROP TABLE booking.guest_tickets, booking.mock_settlements;
      ALTER TABLE booking.bookings DROP COLUMN payment_mode;
      DO $$ DECLARE item record; BEGIN
        FOR item IN SELECT conname FROM pg_constraint
          WHERE conrelid='booking.bookings'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%status%'
        LOOP EXECUTE format('ALTER TABLE booking.bookings DROP CONSTRAINT %I',item.conname); END LOOP;
      END $$;
      ALTER TABLE booking.bookings ADD CHECK(status IN ('PENDING_PAYMENT','CANCELLED','EXPIRED'));
    """)

