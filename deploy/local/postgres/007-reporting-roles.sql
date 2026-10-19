-- LOCAL credentials only. Reporting settings live in a separate PostgreSQL database.
SELECT 'CREATE ROLE analytics_source_dev LOGIN PASSWORD ''analytics_source_dev_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='analytics_source_dev')\gexec
SELECT 'CREATE ROLE analytics_source_test LOGIN PASSWORD ''analytics_source_test_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='analytics_source_test')\gexec
SELECT 'CREATE ROLE metabase_reader LOGIN PASSWORD ''metabase_reader_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='metabase_reader')\gexec
SELECT 'CREATE ROLE metabase_reader_test LOGIN PASSWORD ''metabase_reader_test_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='metabase_reader_test')\gexec
SELECT 'CREATE ROLE metabase_app LOGIN PASSWORD ''metabase_app_local_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='metabase_app')\gexec
SELECT 'CREATE DATABASE wonderland_metabase OWNER metabase_app'
WHERE NOT EXISTS(SELECT FROM pg_database WHERE datname='wonderland_metabase')\gexec
REVOKE CONNECT ON DATABASE wonderland_metabase FROM PUBLIC;
GRANT CONNECT ON DATABASE wonderland_metabase TO metabase_app;
GRANT CONNECT ON DATABASE wonderland TO analytics_source_dev,metabase_reader;
GRANT CONNECT ON DATABASE wonderland_test TO analytics_source_test,metabase_reader_test;
ALTER ROLE metabase_reader SET default_transaction_read_only=on;
ALTER ROLE metabase_reader_test SET default_transaction_read_only=on;
