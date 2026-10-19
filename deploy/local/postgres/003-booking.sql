-- Repeatable bootstrap for new and existing local volumes; contains only development credentials.
SELECT 'CREATE ROLE booking_dev LOGIN PASSWORD ''booking_dev_only'''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'booking_dev')\gexec
GRANT CONNECT ON DATABASE wonderland TO booking_dev;
CREATE SCHEMA IF NOT EXISTS booking AUTHORIZATION booking_dev;
ALTER ROLE booking_dev IN DATABASE wonderland SET search_path = booking;
SELECT 'CREATE ROLE booking_test LOGIN PASSWORD ''booking_test_only'''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'booking_test')\gexec
GRANT CONNECT ON DATABASE wonderland_test TO booking_test;
\connect wonderland_test
CREATE SCHEMA IF NOT EXISTS booking AUTHORIZATION booking_test;
ALTER ROLE booking_test IN DATABASE wonderland_test SET search_path = booking;
