"""Restricted mock event export with independent local analytics acknowledgements."""
from alembic import op

revision = "admission_0002"
down_revision = "admission_0001"


def upgrade():
    op.execute("""
      CREATE TABLE admission.mock_analytics_receipts (
        event_id UUID PRIMARY KEY REFERENCES admission.outbox_events(id),
        delivered_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE VIEW admission.mock_analytics_feed WITH (security_barrier=true) AS
        SELECT id,event_type,aggregate_id,aggregate_version,created_at,
               payload - 'user_sub' AS payload
        FROM admission.outbox_events e
        WHERE event_type IN ('MockGuestCheckedIn','MockRideUsed')
          AND NOT EXISTS (SELECT FROM admission.mock_analytics_receipts r WHERE r.event_id=e.id);
    """)


def downgrade():
    op.execute("DROP VIEW admission.mock_analytics_feed; DROP TABLE admission.mock_analytics_receipts")
