"""Immutable mock arrival/ride facts and privacy-limited reporting views."""
from alembic import op

revision = "analytics_0002"
down_revision = "analytics_0001"


def upgrade():
    op.execute("""
      CREATE TABLE analytics.mock_events (
        event_id UUID PRIMARY KEY, payload_hash VARCHAR(64) NOT NULL,
        admission_id UUID NOT NULL, aggregate_version INTEGER NOT NULL CHECK(aggregate_version>0),
        event_type VARCHAR(60) NOT NULL CHECK(event_type IN ('MockGuestCheckedIn','MockRideUsed')),
        received_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(admission_id,aggregate_version)
      );
      CREATE TABLE analytics.mock_arrivals (
        admission_id UUID PRIMARY KEY, event_id UUID NOT NULL UNIQUE REFERENCES analytics.mock_events(event_id),
        ticket_id UUID NOT NULL UNIQUE, tier_code VARCHAR(20) NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL, recorded_at TIMESTAMPTZ NOT NULL,
        received_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE TABLE analytics.mock_rides (
        ride_id UUID PRIMARY KEY, event_id UUID NOT NULL UNIQUE REFERENCES analytics.mock_events(event_id),
        admission_id UUID NOT NULL, attraction_id UUID NOT NULL,
        attraction_name VARCHAR(120) NOT NULL, category VARCHAR(40) NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL, recorded_at TIMESTAMPTZ NOT NULL,
        received_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE INDEX ix_mock_arrivals_time ON analytics.mock_arrivals(occurred_at);
      CREATE INDEX ix_mock_rides_time ON analytics.mock_rides(occurred_at);
      CREATE VIEW reporting.mock_daily_arrivals AS
        SELECT (occurred_at AT TIME ZONE 'Asia/Colombo')::date AS visit_date,
               tier_code, count(*)::bigint AS guest_arrivals, 'MOCK'::text AS mode
        FROM analytics.mock_arrivals GROUP BY 1,2;
      CREATE VIEW reporting.mock_popular_rides AS
        SELECT (occurred_at AT TIME ZONE 'Asia/Colombo')::date AS visit_date,
               attraction_id::text AS attraction_key,
               (array_agg(attraction_name ORDER BY recorded_at DESC,ride_id DESC))[1] AS attraction_name,
               (array_agg(category ORDER BY recorded_at DESC,ride_id DESC))[1] AS category,
               count(*)::bigint AS ride_uses, count(DISTINCT admission_id)::bigint AS unique_guests,
               'MOCK'::text AS mode
        FROM analytics.mock_rides GROUP BY 1,2;
      CREATE VIEW reporting.mock_hourly_activity AS
        WITH times AS (
          SELECT occurred_at, 1 AS arrivals,0 AS rides FROM analytics.mock_arrivals
          UNION ALL SELECT occurred_at,0,1 FROM analytics.mock_rides
        ) SELECT (occurred_at AT TIME ZONE 'Asia/Colombo')::date AS visit_date,
          extract(hour FROM occurred_at AT TIME ZONE 'Asia/Colombo')::integer AS hour_of_day,
          sum(arrivals)::bigint AS guest_arrivals, sum(rides)::bigint AS ride_uses,'MOCK'::text AS mode
        FROM times GROUP BY 1,2;
      CREATE VIEW reporting.mock_daily_hour_grid AS
        WITH dates AS (SELECT DISTINCT visit_date FROM reporting.mock_hourly_activity)
        SELECT d.visit_date,h.hour_of_day,coalesce(a.guest_arrivals,0)::bigint AS guest_arrivals,
               coalesce(a.ride_uses,0)::bigint AS ride_uses,'MOCK'::text AS mode
        FROM dates d CROSS JOIN generate_series(0,23) h(hour_of_day)
        LEFT JOIN reporting.mock_hourly_activity a USING(visit_date,hour_of_day);
      CREATE VIEW reporting.mock_pipeline_health AS
        SELECT (SELECT count(*) FROM analytics.mock_arrivals)::bigint AS total_guest_arrivals,
          (SELECT count(*) FROM analytics.mock_rides)::bigint AS total_ride_uses,
          (SELECT max(recorded_at) FROM (SELECT recorded_at FROM analytics.mock_arrivals UNION ALL SELECT recorded_at FROM analytics.mock_rides) q) AS latest_source_recorded_at,
          (SELECT max(received_at) FROM analytics.mock_events) AS latest_ingested_at,
          (SELECT coalesce(max(extract(epoch FROM received_at-recorded_at)),0) FROM (SELECT received_at,recorded_at FROM analytics.mock_arrivals UNION ALL SELECT received_at,recorded_at FROM analytics.mock_rides) q) AS max_delivery_lag_seconds,
          (SELECT count(*) FROM analytics.mock_rides r WHERE NOT EXISTS(SELECT FROM analytics.mock_arrivals a WHERE a.admission_id=r.admission_id))::bigint AS rides_awaiting_arrival,
          'MOCK'::text AS mode;
    """)


def downgrade():
    op.execute("DROP VIEW reporting.mock_pipeline_health,reporting.mock_daily_hour_grid,reporting.mock_hourly_activity,reporting.mock_popular_rides,reporting.mock_daily_arrivals; DROP TABLE analytics.mock_rides,analytics.mock_arrivals,analytics.mock_events")
