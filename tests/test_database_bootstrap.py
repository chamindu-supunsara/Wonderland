import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy/database_bootstrap"))
from db_bootstrap import bootstrap as module  # noqa: E402


def test_rejects_foreign_existing_credential():
    class Client:
        def describe_secret(self, **kwargs):
            return {"VersionIdsToStages": {"id": ["AWSCURRENT"]}}

        def get_secret_value(self, **kwargs):
            return {"SecretString": json.dumps({"host": "another-host", "password": "x" * 40})}

    cfg = module.Config(
        "expected", "master", {s: s for s in module.SERVICES}, "/ca", ROOT / "services"
    )
    with pytest.raises(ValueError, match="does not match"):
        module.service_credentials(Client(), cfg, "catalog")


def test_production_errors_do_not_print_credentials(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_HOST", "wonderland-demo.test.ap-south-1.rds.amazonaws.com")
    monkeypatch.setenv("MASTER_SECRET_ARN", "master")
    monkeypatch.setenv("SERVICE_SECRET_ARNS", json.dumps({s: s for s in module.SERVICES}))

    def fail(*args, **kwargs):
        raise RuntimeError("DO_NOT_LEAK_SUPER_SECRET_PASSWORD")

    monkeypatch.setattr(module.boto3, "client", fail)
    assert module.main() == 1
    output = capsys.readouterr()
    assert "DO_NOT_LEAK" not in output.out + output.err
    assert "BOOTSTRAP_FAILED=RuntimeError" in output.out


def test_owner_merge_guard_preserves_baseline_and_rejects_tampering(tmp_path):
    import subprocess

    source = (ROOT / "infra/database/apply-access-cloudshell.sh").read_text()
    guard = source.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    proposal = json.loads((ROOT / "infra/database/operator-policy.json").read_text())
    template = json.loads((ROOT / "infra/database/bootstrap-access.json").read_text())
    baseline = {"Version": "2012-10-17", "Statement": []}
    for name in [
        "infra/feasibility/operator-policy.json",
        "infra/terraform/bootstrap/operator-policy.json",
        "infra/terraform/foundation/operator-policy.json",
    ]:
        baseline["Statement"] += json.loads((ROOT / name).read_text())["Statement"]
    for case in ["valid", "changed_template", "broadened_policy", "drift"]:
        folder = tmp_path / case
        folder.mkdir()
        policy = json.loads(json.dumps(proposal))
        candidate = json.loads(json.dumps(template))
        existing = json.loads(json.dumps(baseline))
        if case == "changed_template":
            candidate["Resources"]["BootstrapRole"]["Properties"]["Policies"][0]["PolicyDocument"][
                "Statement"
            ][0]["Resource"] = "*"
        if case == "broadened_policy":
            policy["Statement"][0]["Resource"] = "*"
        if case == "drift":
            existing["Statement"][0]["Resource"] = "*"
        (folder / "operator-policy.json").write_text(json.dumps(policy))
        (folder / "bootstrap-access.json").write_text(json.dumps(candidate))
        (folder / "before.json").write_text(json.dumps({"InlinePolicy": json.dumps(existing)}))
        result = subprocess.run(
            [sys.executable, "-c", guard, str(folder), str(folder)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert (result.returncode == 0) == (case == "valid")
        if case == "valid":
            merged = json.loads((folder / "merged.json").read_text())
            assert merged["Statement"] == baseline["Statement"] + proposal["Statement"]
        else:
            assert not (folder / "merged.json").exists()
