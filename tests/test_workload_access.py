import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "workload_access", ROOT / "infra/terraform/workloads/verify_access.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_reviewed_policy_and_baseline_are_pinned(tmp_path):
    directory = ROOT / "infra/terraform/workloads"
    baseline = {"Version": "2012-10-17", "Statement": []}
    for source in [
        "infra/feasibility/operator-policy.json",
        "infra/terraform/bootstrap/operator-policy.json",
        "infra/terraform/foundation/operator-policy.json",
        "infra/database/operator-policy.json",
    ]:
        baseline["Statement"].extend(json.loads((ROOT / source).read_text())["Statement"])
    current = {"InlinePolicy": json.dumps(baseline)}
    policy = guard.verify(directory, current)
    assert not any(
        "secretsmanager:" in action
        for statement in policy["Statement"]
        for action in (
            [statement["Action"]] if isinstance(statement["Action"], str) else statement["Action"]
        )
    )
    changed = json.loads(json.dumps(policy))
    changed["Statement"][0]["Resource"] = "*"
    (tmp_path / "operator-policy.json").write_text(json.dumps(changed))
    with pytest.raises(AssertionError, match="Unreviewed"):
        guard.verify(tmp_path, current)
    with pytest.raises(AssertionError, match="drift"):
        guard.verify(directory, {"InlinePolicy": '{"Version":"2012-10-17","Statement":[]}'})
