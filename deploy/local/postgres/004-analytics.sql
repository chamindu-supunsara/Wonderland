-- Local-only service isolation. Run explicitly on existing volumes through events-bootstrap.
SELECT 'CREATE ROLE analytics_dev LOGIN PASSWORD ''analytics_dev_only'''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_dev')\gexec
GRANT CONNECT ON DATABASE wonderland TO analytics_dev;
CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION analytics_dev;
CREATE SCHEMA IF NOT EXISTS reporting AUTHORIZATION analytics_dev;
ALTER ROLE analytics_dev IN DATABASE wonderland SET search_path = analytics;
SELECT 'CREATE ROLE analytics_test LOGIN PASSWORD ''analytics_test_only'''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_test')\gexec
GRANT CONNECT ON DATABASE wonderland_test TO analytics_test;
\connect wonderland_test
CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION analytics_test;
CREATE SCHEMA IF NOT EXISTS reporting AUTHORIZATION analytics_test;
ALTER ROLE analytics_test IN DATABASE wonderland_test SET search_path = analytics;

