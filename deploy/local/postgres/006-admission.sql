-- Local demonstration roles only. No access to Booking, Payment or Catalog schemas.
SELECT 'CREATE ROLE admission_dev LOGIN PASSWORD ''admission_dev_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='admission_dev')\gexec
GRANT CONNECT ON DATABASE wonderland TO admission_dev;
CREATE SCHEMA IF NOT EXISTS admission AUTHORIZATION admission_dev;
ALTER ROLE admission_dev IN DATABASE wonderland SET search_path=admission;
SELECT 'CREATE ROLE admission_test LOGIN PASSWORD ''admission_test_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='admission_test')\gexec
GRANT CONNECT ON DATABASE wonderland_test TO admission_test;
\connect wonderland_test
CREATE SCHEMA IF NOT EXISTS admission AUTHORIZATION admission_test;
ALTER ROLE admission_test IN DATABASE wonderland_test SET search_path=admission;
