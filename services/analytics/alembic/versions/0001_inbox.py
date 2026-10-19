"""Initial durable analytics event receipt and booking lifecycle projection."""
from alembic import op
revision = "analytics_0001"
down_revision = None

def upgrade():
    op.execute("""
        CREATE TABLE analytics.event_inbox (
          consumer VARCHAR(80) NOT NULL, event_id UUID NOT NULL, payload_hash VARCHAR(64) NOT NULL,
          received_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(consumer,event_id)
        );
        CREATE TABLE analytics.booking_projection (
          booking_id UUID PRIMARY KEY, version INTEGER NOT NULL CHECK(version > 0),
          payload JSONB NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

def downgrade():
    op.execute("DROP TABLE analytics.booking_projection, analytics.event_inbox")

