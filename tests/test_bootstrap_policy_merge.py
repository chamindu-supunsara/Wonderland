"""Exercise the exact owner-helper guard without executing any AWS command."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "infra/terraform/bootstrap"


def merge(tmp_path, policy):
    source = (DIRECTORY / "apply-permissions-cloudshell.sh").read_text()
    guard = source.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    old = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ExistingPermissions",
                "Effect": "Allow",
                "Action": "eks:ListClusters",
                "Resource": "*",
            }
        ],
    }
    new_path, old_path, output = [
        tmp_path / name for name in ["new.json", "old.json", "merged.json"]
    ]
    new_path.write_text(json.dumps(policy))
    old_path.write_text(json.dumps({"InlinePolicy": json.dumps(old)}))
    result = subprocess.run(
        [sys.executable, "-c", guard, str(new_path), str(old_path), str(output)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result, output, old


def test_preserves_existing_grants_and_accepts_single_action(tmp_path):
    policy = json.loads((DIRECTORY / "operator-policy.json").read_text())
    result, output, old = merge(tmp_path, policy)
    assert result.returncode == 0, result.stderr
    combined = json.loads(output.read_text())
    assert combined["Statement"] == old["Statement"] + policy["Statement"]


@pytest.mark.parametrize("change", ["wildcard_resource", "extra_action", "unknown_statement"])
def test_refuses_unreviewed_permissions(tmp_path, change):
    policy = json.loads((DIRECTORY / "operator-policy.json").read_text())
    if change == "wildcard_resource":
        policy["Statement"][0]["Resource"] = "*"
    elif change == "extra_action":
        policy["Statement"][0]["Action"].append("iam:CreateRole")
    else:
        policy["Statement"][0]["Sid"] = "UnreviewedGrant"
    result, output, _ = merge(tmp_path, policy)
    assert result.returncode != 0
    assert not output.exists()
