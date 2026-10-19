"""Worker heartbeat is separate from historical data timestamps."""
from alembic import op

revision = "analytics_0003"
down_revision = "analytics_0002"


def upgrade():
    op.execute("""
      CREATE TABLE analytics.mock_pipeline_state (
        id INTEGER PRIMARY KEY CHECK(id=1), polled_at TIMESTAMPTZ NOT NULL,
        pending_events BIGINT NOT NULL, retained_errors INTEGER NOT NULL,
        oldest_pending_recorded_at TIMESTAMPTZ
      );
      CREATE VIEW reporting.mock_worker_health AS
        SELECT polled_at AS worker_last_polled_at,
          extract(epoch FROM now()-polled_at) AS heartbeat_age_seconds,
          pending_events,retained_errors,oldest_pending_recorded_at,'MOCK'::text AS mode
        FROM analytics.mock_pipeline_state WHERE id=1;
    """)


def downgrade():
    op.execute("DROP VIEW reporting.mock_worker_health; DROP TABLE analytics.mock_pipeline_state")
