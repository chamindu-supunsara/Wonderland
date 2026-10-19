-- Separate test database: pytest never resets the development catalog.
CREATE ROLE catalog_test LOGIN PASSWORD 'catalog_test_only';
CREATE DATABASE wonderland_test OWNER catalog_test;
\connect wonderland_test
CREATE SCHEMA catalog AUTHORIZATION catalog_test;
ALTER ROLE catalog_test IN DATABASE wonderland_test SET search_path = catalog;

