"""Catalog price outbox."""
from alembic import op
revision = "0003_event_outbox"
down_revision = "0002_admin_catalog"

def upgrade():
    op.execute("""
        CREATE TABLE catalog.outbox_events (
          id UUID PRIMARY KEY, aggregate_id UUID NOT NULL, aggregate_version INTEGER NOT NULL,
          event_type VARCHAR(80) NOT NULL, payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(), published_at TIMESTAMPTZ,
          sns_message_id VARCHAR(100), attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(), failed_at TIMESTAMPTZ,
          last_error VARCHAR(120), CHECK (attempts >= 0 AND aggregate_version > 0)
        );
        CREATE INDEX ix_catalog_outbox_pending ON catalog.outbox_events(next_attempt_at,created_at)
          WHERE published_at IS NULL AND failed_at IS NULL;
    """)

def downgrade():
    op.execute("DROP TABLE catalog.outbox_events")

