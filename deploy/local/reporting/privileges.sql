-- Run after migrations. Grant named reporting surfaces, never operational/base tables.
GRANT USAGE ON SCHEMA admission TO analytics_source_dev;
GRANT SELECT ON admission.mock_analytics_feed TO analytics_source_dev;
GRANT INSERT ON admission.mock_analytics_receipts TO analytics_source_dev;
GRANT USAGE ON SCHEMA reporting TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO metabase_reader;
\connect wonderland_test
DO $$ BEGIN
  IF to_regclass('admission.mock_analytics_feed') IS NOT NULL THEN
    GRANT USAGE ON SCHEMA admission TO analytics_source_test;
    GRANT SELECT ON admission.mock_analytics_feed TO analytics_source_test;
    GRANT INSERT ON admission.mock_analytics_receipts TO analytics_source_test;
  END IF;
  IF to_regnamespace('reporting') IS NOT NULL THEN
    GRANT USAGE ON SCHEMA reporting TO metabase_reader_test;
    GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO metabase_reader_test;
  END IF;
END $$;
