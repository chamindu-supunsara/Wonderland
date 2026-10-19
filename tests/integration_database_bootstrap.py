"""Run only inside the isolated Step10B Docker network; never against AWS or local app data."""

import json
import secrets
from pathlib import Path

import psycopg
from db_bootstrap.bootstrap import SERVICES, Config, bootstrap, connect
from psycopg import sql


class MemorySecrets:
    def __init__(self, master):
        self.values = {"master": master}
        self.writes = 0

    def describe_secret(self, SecretId):
        return {
            "VersionIdsToStages": {"version": ["AWSCURRENT"]} if SecretId in self.values else {}
        }

    def get_secret_value(self, SecretId):
        return {"SecretString": json.dumps(self.values[SecretId])}

    def put_secret_value(self, SecretId, SecretString):
        self.values[SecretId] = json.loads(SecretString)
        self.writes += 1


def main():
    password = Path("/test-password").read_text().strip()
    ca = "/test/certs/ca.pem"
    master_password = secrets.token_urlsafe(48)
    with psycopg.connect(
        host="postgres",
        dbname="postgres",
        user="test_root",
        password=password,
        sslmode="verify-full",
        sslrootcert=ca,
        autocommit=True,
    ) as root:
        root.execute(
            sql.SQL("CREATE ROLE bootstrap_admin LOGIN CREATEDB CREATEROLE PASSWORD {}").format(
                sql.Literal(master_password)
            )
        )
        root.execute("CREATE DATABASE wonderland OWNER bootstrap_admin")
    config = Config("postgres", "master", {s: s for s in SERVICES}, ca, Path("/app/services"))
    client = MemorySecrets(
        {"host": "postgres", "username": "bootstrap_admin", "password": master_password}
    )
    delivered = {}
    first = bootstrap(
        config, client, lambda service, value: delivered.update({service: value["DATABASE_URL"]})
    )
    assert first["status"] == "VERIFIED" and first["hostname_mismatch_rejected"]
    assert set(delivered) == set(SERVICES)
    old_passwords = {s: client.values[s]["password"] for s in SERVICES}
    writes = client.writes
    with connect(
        config, client.values["catalog"]["username"], old_passwords["catalog"], autocommit=True
    ) as runtime:
        runtime.execute(
            "UPDATE catalog.attractions SET description='Cloud administrator edit' "
            "WHERE seed_key='skyline-rush'"
        )
        try:
            runtime.execute("SELECT * FROM booking.visit_slots LIMIT 1")
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("Cross-schema SELECT unexpectedly succeeded")
        try:
            runtime.execute("CREATE TABLE catalog.runtime_must_not_create (id int)")
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("Runtime DDL unexpectedly succeeded")
    second = bootstrap(config, client, lambda service, value: None)
    assert second["seed_counts"] == first["seed_counts"]
    assert client.writes == writes
    assert old_passwords == {s: client.values[s]["password"] for s in SERVICES}
    with connect(config, client.values["catalog"]["username"], old_passwords["catalog"]) as runtime:
        assert (
            runtime.execute(
                "SELECT description FROM catalog.attractions WHERE seed_key='skyline-rush'"
            ).fetchone()[0]
            == "Cloud administrator edit"
        )
    try:
        psycopg.connect(
            host="postgres",
            dbname="wonderland_metabase",
            user="wl_catalog",
            password=old_passwords["catalog"],
            sslmode="verify-full",
            sslrootcert=ca,
        )
    except psycopg.Error as error:
        assert 'permission denied for database "wonderland_metabase"' in str(error)
    else:
        raise AssertionError("Application login reached Metabase metadata database")
    try:
        psycopg.connect(
            host="postgres",
            dbname="wonderland",
            user="bootstrap_admin",
            password=master_password,
            sslmode="verify-full",
            sslrootcert="/test/certs/untrusted-ca.pem",
        )
    except psycopg.OperationalError as error:
        assert "certificate verify failed" in str(error).lower()
    else:
        raise AssertionError("Untrusted CA was accepted")
    from integration_cloud_events import check_events

    cloud_events = check_events(delivered)
    print(
        json.dumps(
            {
                "status": "PASSED",
                "migrations": second["migrations"],
                "seed_counts": second["seed_counts"],
                "two_runs_same_credentials_and_seed_counts": True,
                "administrator_edit_preserved": True,
                "runtime_cross_schema_select_denied": True,
                "runtime_ddl_denied": True,
                "metabase_connect_denied": True,
                "untrusted_ca_rejected": True,
                "wrong_hostname_rejected": True,
                "master_is_not_superuser": True,
                "cloud_access": False,
                "cloud_event_handlers": cloud_events,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
