"""Immutable simulated purchases and cloud worker polling freshness."""
from alembic import op

revision = 'analytics_0004'
down_revision = 'analytics_0003'


def upgrade():
    op.execute("""
      CREATE TABLE analytics.mock_purchases (
        booking_id UUID PRIMARY KEY, event_id UUID NOT NULL UNIQUE,
        tier_code VARCHAR(20) NOT NULL CHECK(tier_code IN ('INDIVIDUAL','COUPLE','FAMILY','GROUP')),
        guest_count INTEGER NOT NULL CHECK(guest_count BETWEEN 1 AND 5),
        amount_minor INTEGER NOT NULL CHECK(amount_minor>0),
        currency VARCHAR(3) NOT NULL CHECK(currency='USD'),
        confirmed_at TIMESTAMPTZ NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE VIEW reporting.mock_daily_purchases AS
        SELECT (confirmed_at AT TIME ZONE 'Asia/Colombo')::date AS purchase_date,
          tier_code,currency,count(*)::bigint AS purchases,
          sum(guest_count)::bigint AS guest_tickets,
          sum(amount_minor)::bigint AS simulated_revenue_minor,'MOCK'::text AS mode
        FROM analytics.mock_purchases GROUP BY 1,2,3;
      CREATE VIEW reporting.mock_purchase_totals AS
        SELECT count(*)::bigint AS purchases,coalesce(sum(guest_count),0)::bigint AS guest_tickets,
          coalesce(sum(amount_minor),0)::bigint AS simulated_revenue_minor,
          'USD'::text AS currency,'MOCK'::text AS mode FROM analytics.mock_purchases;
      CREATE TABLE analytics.cloud_worker_state (
        worker_name VARCHAR(60) PRIMARY KEY,
        last_polled_at TIMESTAMPTZ NOT NULL, last_batch_messages INTEGER NOT NULL
      );
      CREATE VIEW reporting.cloud_worker_health AS
        SELECT worker_name,last_polled_at,
          extract(epoch FROM now()-last_polled_at) AS heartbeat_age_seconds,
          last_batch_messages,'MOCK'::text AS mode FROM analytics.cloud_worker_state;
    """)


def downgrade():
    op.execute('DROP VIEW reporting.cloud_worker_health, reporting.mock_purchase_totals, reporting.mock_daily_purchases; DROP TABLE analytics.cloud_worker_state, analytics.mock_purchases')
