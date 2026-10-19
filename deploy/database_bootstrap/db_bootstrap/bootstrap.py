"""In-cluster bootstrap. Credentials stay in memory, Secrets Manager and scoped K8s Secrets."""

import base64
import importlib
import json
import os
import re
import secrets
import socket
import ssl
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import boto3
import psycopg
from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from psycopg import sql
from sqlalchemy import URL, create_engine, text

SERVICES = ("catalog", "booking", "payment", "admission", "analytics")
REPORT_VIEWS = (
    "mock_daily_arrivals", "mock_popular_rides", "mock_hourly_activity",
    "mock_daily_hour_grid", "mock_pipeline_health", "mock_worker_health",
)


@dataclass(frozen=True)
class Config:
    host: str
    master_secret: str
    service_secrets: dict
    ca_file: str
    services_root: Path
    database: str = "wonderland"


def db_url(config, username, password):
    return URL.create("postgresql+psycopg", username=username, password=password,
                      host=config.host, port=5432, database=config.database,
                      query={"sslmode": "verify-full", "sslrootcert": config.ca_file,
                             "connect_timeout": "10"})


def connect(config, username, password, **extra):
    return psycopg.connect(host=config.host, port=5432, dbname=config.database,
                          user=username, password=password, sslmode="verify-full",
                          sslrootcert=config.ca_file, connect_timeout=10, **extra)


def service_credentials(client, config, service):
    arn = config.service_secrets[service]
    metadata = client.describe_secret(SecretId=arn)
    if metadata.get("VersionIdsToStages"):
        value = json.loads(client.get_secret_value(SecretId=arn)["SecretString"])
        if any(value.get(key) != expected for key, expected in {
            "service": service, "host": config.host, "dbname": config.database,
            "username": f"wl_{service}", "schema_version": 1,
        }.items()) or not isinstance(value.get("password"), str) or len(value["password"]) < 32:
            raise ValueError("Existing credential metadata does not match this deployment")
    else:
        value = {"schema_version": 1, "service": service, "host": config.host,
                 "port": 5432, "dbname": config.database, "username": f"wl_{service}",
                 "password": secrets.token_urlsafe(48), "status": "prepared"}
        # Persist first: after any crash, retry reuses the same credential rather than rotating it.
        client.put_secret_value(SecretId=arn, SecretString=json.dumps(value))
    value["sslmode"] = "verify-full"
    value["sslrootcert"] = config.ca_file
    value["DATABASE_URL"] = db_url(config, value["username"], value["password"]).render_as_string(hide_password=False)
    return value


def ensure_role(admin, name, password=None):
    found = admin.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s", (name,)).fetchone()
    if found and any(found):
        raise ValueError("Refusing an unexpectedly privileged existing role")
    if not found:
        admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))
    if password is None:
        admin.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(sql.Identifier(name)))
    else:
        admin.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(name), sql.Literal(password)))


def ensure_schema(admin, schema, owner):
    existing = admin.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone()
    if existing and existing[0] != owner:
        raise ValueError("Existing schema has an unexpected owner")
    admin.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(sql.Identifier(schema), sql.Identifier(owner)))
    admin.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(schema)))


def migrate(config, master, service):
    cfg = AlembicConfig(str(config.services_root / service / "alembic.ini"))
    cfg.set_main_option("script_location", str(config.services_root / service / "alembic"))
    engine = create_engine(db_url(config, master["username"], master["password"]), hide_parameters=True)
    try:
        with engine.begin() as connection:
            # Fixed allowlisted identifiers only. A supplied connection keeps admin credentials
            # out of service configuration and runs DDL as the service's NOLOGIN owner.
            connection.execute(text(f'SET LOCAL ROLE "wl_{service}_owner"'))
            connection.execute(text(f'SET LOCAL search_path TO "{service}"'))
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            heads = connection.execute(text(f'SELECT version_num FROM "{service}".alembic_version')).scalars().all()
            if set(heads) != set(ScriptDirectory.from_config(cfg).get_heads()):
                raise ValueError("Migration head verification failed")
            return heads
    finally:
        engine.dispose()


def runtime_grants(admin, service):
    owner, user = f"wl_{service}_owner", f"wl_{service}"
    admin.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(service), sql.Identifier(user)))
    admin.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(sql.Identifier(service), sql.Identifier(user)))
    admin.execute(sql.SQL("GRANT USAGE,SELECT,UPDATE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(sql.Identifier(service), sql.Identifier(user)))
    admin.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {}").format(sql.Identifier(owner), sql.Identifier(service), sql.Identifier(user)))
    admin.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT USAGE,SELECT,UPDATE ON SEQUENCES TO {}").format(sql.Identifier(owner), sql.Identifier(service), sql.Identifier(user)))
    admin.execute(sql.SQL("REVOKE ALL ON {}.alembic_version FROM {}").format(sql.Identifier(service), sql.Identifier(user)))


def publish_runtime_secret(service, value):
    # Role/RoleBinding permit patching only the five precreated runtime Secrets.
    host = os.environ["KUBERNETES_SERVICE_HOST"]
    port = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
    token = Path("/var/run/secrets/kubernetes.io/serviceaccount/token").read_text().strip()
    ca = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    url = f"https://{host}:{port}/api/v1/namespaces/wonderland/secrets/wonderland-{service}"
    request = urllib.request.Request(url, method="PATCH", data=json.dumps({"data": {
        "DATABASE_URL": base64.b64encode(value["DATABASE_URL"].encode()).decode(),
    }}).encode(), headers={"Authorization": f"Bearer {token}", "Content-Type": "application/merge-patch+json"})
    with urllib.request.urlopen(request, context=ssl.create_default_context(cafile=ca), timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("Runtime secret delivery failed")


def verify_runtime(config, values, admin):
    result = {}
    for service in SERVICES:
        value = values[service]
        with connect(config, value["username"], value["password"], autocommit=True) as connection:
            tls = connection.execute("SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()").fetchone()
            if not tls or not tls[0]:
                raise ValueError("TLS not active")
            own_usage, own_create = connection.execute("SELECT has_schema_privilege(current_user,%s,'USAGE'),has_schema_privilege(current_user,%s,'CREATE')", (service, service)).fetchone()
            if not own_usage or own_create:
                raise ValueError("Runtime DDL isolation failed")
            for other in SERVICES:
                if other != service and connection.execute("SELECT has_schema_privilege(current_user,%s,'USAGE')", (other,)).fetchone()[0]:
                    raise ValueError("Cross-service schema isolation failed")
            if connection.execute("SELECT has_table_privilege(current_user,%s,'SELECT')", (f"{service}.alembic_version",)).fetchone()[0]:
                raise ValueError("Runtime can access migration metadata")
            result[service] = {"tls": tls[1], "own_schema_usage": True, "runtime_ddl_denied": True, "cross_schema_usage_denied": True, "migration_metadata_denied": True}
    with admin.transaction():
        admin.execute("SET LOCAL ROLE wl_reporting_reader")
        for view in REPORT_VIEWS:
            admin.execute(sql.SQL("SELECT * FROM reporting.{} LIMIT 1").format(sql.Identifier(view))).fetchall()
        if admin.execute("SELECT has_schema_privilege(current_user,'analytics','USAGE')").fetchone()[0]:
            raise ValueError("Reporting role can access raw analytics")
    # A reachable server with the wrong hostname must fail certificate verification.
    sample = values["catalog"]
    try:
        bad = psycopg.connect(host=socket.gethostbyname(config.host), port=5432,
                              dbname=config.database, user=sample["username"], password=sample["password"],
                              sslmode="verify-full", sslrootcert=config.ca_file, connect_timeout=10)
    except psycopg.OperationalError as error:
        if "does not match host name" not in str(error).lower():
            raise ValueError("Hostname negative test did not reach the expected TLS rejection") from None
    else:
        bad.close()
        raise ValueError("TLS hostname mismatch was incorrectly accepted")
    return result


def bootstrap(config, client, publish=publish_runtime_secret):
    if set(config.service_secrets) != set(SERVICES):
        raise ValueError("Exactly five service-secret destinations are required")
    master = json.loads(client.get_secret_value(SecretId=config.master_secret)["SecretString"])
    if master.get("host", config.host) != config.host or not master.get("password"):
        raise ValueError("Master secret does not match the target host")
    values, heads = {}, {}
    with connect(config, master["username"], master["password"], autocommit=True) as admin:
        admin.execute("SELECT pg_advisory_lock(hashtextextended('wonderland:cloud-bootstrap',0))")
        admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(config.database)))
        admin.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for service in SERVICES:
            value = service_credentials(client, config, service)
            values[service] = value
            owner = f"wl_{service}_owner"
            ensure_role(admin, owner)
            ensure_role(admin, value["username"], value["password"])
            admin.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(owner), sql.Identifier(master["username"])))
            admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {},{}").format(sql.Identifier(config.database), sql.Identifier(owner), sql.Identifier(value["username"])))
            ensure_schema(admin, service, owner)
        ensure_schema(admin, "reporting", "wl_analytics_owner")
        ensure_role(admin, "wl_reporting_reader")
        ensure_role(admin, "wl_metabase_owner")
        admin.execute(sql.SQL("GRANT wl_reporting_reader TO {}").format(sql.Identifier(master["username"])))
        admin.execute(sql.SQL("GRANT wl_metabase_owner TO {}").format(sql.Identifier(master["username"])))
        if not admin.execute("SELECT 1 FROM pg_database WHERE datname='wonderland_metabase'").fetchone():
            admin.execute("CREATE DATABASE wonderland_metabase OWNER wl_metabase_owner")
        admin.execute("REVOKE ALL ON DATABASE wonderland_metabase FROM PUBLIC")
        for service in SERVICES:
            heads[service] = migrate(config, master, service)
            runtime_grants(admin, service)
        admin.execute("GRANT USAGE ON SCHEMA reporting TO wl_reporting_reader,wl_analytics")
        for view in REPORT_VIEWS:
            admin.execute(sql.SQL("GRANT SELECT ON reporting.{} TO wl_reporting_reader,wl_analytics").format(sql.Identifier(view)))
        # Seed only demo inventory/pricing and future visit slots. No users or fake purchases.
        for service, module in [("catalog", "app.seed"), ("booking", "booking_app.seed")]:
            os.environ["DATABASE_URL"] = values[service]["DATABASE_URL"]
            importlib.import_module(module).seed()
        verified = verify_runtime(config, values, admin)
        counts = {"attractions": admin.execute("SELECT count(*) FROM catalog.attractions").fetchone()[0],
                  "ticket_tiers": admin.execute("SELECT count(*) FROM catalog.ticket_tiers").fetchone()[0],
                  "visit_slots": admin.execute("SELECT count(*) FROM booking.visit_slots").fetchone()[0]}
        if counts["attractions"] < 4 or counts["ticket_tiers"] < 4 or counts["visit_slots"] < 21:
            raise ValueError("Seed verification failed")
        for service in SERVICES:
            values[service]["status"] = "ready"
            current = json.loads(client.get_secret_value(SecretId=config.service_secrets[service])["SecretString"])
            if current != values[service]:
                client.put_secret_value(SecretId=config.service_secrets[service], SecretString=json.dumps(values[service]))
            publish(service, values[service])
        return {"status": "VERIFIED", "migrations": heads, "runtime_roles": verified, "seed_counts": counts,
                "reporting_views_only": True, "metabase_database_private_roles_prepared": True,
                "hostname_mismatch_rejected": True, "service_credentials_reused_on_retry": True,
                "checkout": "mock", "credentials_logged": False}


def main():
    try:
        host = os.environ["DATABASE_HOST"]
        if not re.fullmatch(r"wonderland-demo\.[a-z0-9]+\.ap-south-1\.rds\.amazonaws\.com", host):
            raise ValueError("Unexpected production database host")
        config = Config(host, os.environ["MASTER_SECRET_ARN"], json.loads(os.environ["SERVICE_SECRET_ARNS"]),
                        "/app/certs/rds-global-bundle.pem", Path("/app/services"))
        result = bootstrap(config, boto3.client("secretsmanager", region_name="ap-south-1"))
        print("BOOTSTRAP_REPORT=" + json.dumps(result, sort_keys=True), flush=True)
        return 0
    except Exception as error:
        # Database/AWS/HTTP exceptions can contain SQL parameters or response payloads.
        # Deliberately omit their messages/tracebacks from Kubernetes logs.
        print("BOOTSTRAP_FAILED=" + type(error).__name__ + "; inspect controlled verification, no credentials emitted", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
