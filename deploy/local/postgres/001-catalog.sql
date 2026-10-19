-- Local-only credentials. Cloud identities/secrets are a later milestone.
CREATE ROLE catalog_dev LOGIN PASSWORD 'catalog_dev_only';
GRANT CONNECT ON DATABASE wonderland TO catalog_dev;
CREATE SCHEMA catalog AUTHORIZATION catalog_dev;
-- Alembic uses its version table in this dedicated schema.
ALTER ROLE catalog_dev IN DATABASE wonderland SET search_path = catalog;

