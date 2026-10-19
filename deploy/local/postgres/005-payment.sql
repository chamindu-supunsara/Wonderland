-- Local development simulator; each service retains separate schema permissions.
SELECT 'CREATE ROLE payment_dev LOGIN PASSWORD ''payment_dev_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='payment_dev')\gexec
GRANT CONNECT ON DATABASE wonderland TO payment_dev;
CREATE SCHEMA IF NOT EXISTS payment AUTHORIZATION payment_dev;
ALTER ROLE payment_dev IN DATABASE wonderland SET search_path=payment;
SELECT 'CREATE ROLE payment_test LOGIN PASSWORD ''payment_test_only'''
WHERE NOT EXISTS(SELECT FROM pg_roles WHERE rolname='payment_test')\gexec
GRANT CONNECT ON DATABASE wonderland_test TO payment_test;
\connect wonderland_test
CREATE SCHEMA IF NOT EXISTS payment AUTHORIZATION payment_test;
ALTER ROLE payment_test IN DATABASE wonderland_test SET search_path=payment;

