"""Development-only checkout records; no real payment proof."""
from alembic import op
revision = "payment_0001"
down_revision = None

def upgrade():
    op.execute("""
      CREATE TABLE payment.mock_checkouts (
        id UUID PRIMARY KEY, booking_id UUID NOT NULL UNIQUE,
        user_sub VARCHAR(128) NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor>0),
        currency VARCHAR(3) NOT NULL, booking_reference VARCHAR(40) NOT NULL,
        status VARCHAR(15) NOT NULL CHECK(status IN ('READY','DECIDED','SUCCEEDED','FAILED','REJECTED')),
        outcome VARCHAR(10) CHECK(outcome IN ('success','failure')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE INDEX ix_payment_owner ON payment.mock_checkouts(user_sub);
    """)

def downgrade():
    op.execute("DROP TABLE payment.mock_checkouts")

