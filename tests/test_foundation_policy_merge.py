"""Guard the actual permission merger against policy expansion and owner-side drift."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "foundation_merge", ROOT / "infra/terraform/foundation/merge_operator_policy.py"
)
merger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merger)


def policies():
    old = {"Version": "2012-10-17", "Statement": []}
    for name in [
        "infra/feasibility/operator-policy.json",
        "infra/terraform/bootstrap/operator-policy.json",
    ]:
        old["Statement"] += json.loads((ROOT / name).read_text())["Statement"]
    proposal = json.loads((ROOT / "infra/terraform/foundation/operator-policy.json").read_text())
    return proposal, old


def test_preserves_existing_and_is_idempotent():
    proposal, old = policies()
    original = copy.deepcopy(old)
    merged = merger.merge(proposal, old)
    assert old == original
    assert merged["Statement"] == old["Statement"] + proposal["Statement"]
    assert merger.merge(proposal, merged) == merged
    assert len(json.dumps(merged, separators=(",", ":")).encode()) <= 10240


@pytest.mark.parametrize("change", ["resource", "action", "condition", "duplicate"])
def test_rejects_modified_proposal(change):
    proposal, old = policies()
    if change == "resource":
        proposal["Statement"][0]["Resource"] = "*"
    elif change == "action":
        proposal["Statement"][0]["Action"].append("iam:CreateUser")
    elif change == "condition":
        proposal["Statement"][3].pop("Condition")
    else:
        proposal["Statement"].append(proposal["Statement"][0])
    with pytest.raises(ValueError, match="differs from the reviewed"):
        merger.merge(proposal, old)


def test_rejects_existing_policy_drift():
    proposal, old = policies()
    old["Statement"][0]["Action"].append("cloudformation:UpdateStack")
    with pytest.raises(ValueError, match="changed since review"):
        merger.merge(proposal, old)


def test_rejects_changed_existing_foundation_statement():
    proposal, old = policies()
    merged = merger.merge(proposal, old)
    merged["Statement"][-1]["Resource"] = "*"
    with pytest.raises(ValueError, match="foundation statements differ"):
        merger.merge(proposal, merged)


def test_rejects_over_limit_even_with_reviewed_baseline(monkeypatch):
    proposal, old = policies()
    old["Statement"][0]["Resource"].append("arn:aws:s3:::" + "a" * 10240)
    monkeypatch.setattr(merger, "CURRENT_SHA256", merger.digest(old))
    with pytest.raises(ValueError, match="exceeds 10,240"):
        merger.merge(proposal, old)
