import fnmatch
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_listener_rules_cover_each_api_route_within_aws_match_limits():
    # Read the checked-in rule declarations, not a developer's ignored plan file.
    source = (ROOT / "infra/terraform/routing/network.tf").read_text()
    rules = []
    for match in re.finditer(
        r'resource "aws_lb_listener_rule" "([^\"]+)" \{(.*?)(?=\nresource|\Z)', source, re.S
    ):
        name, body = match.groups()
        patterns = []
        for pattern in re.finditer(
            r"path_pattern\s*\{\s*(regex_values|values)\s*=\s*(\[[^\]]+\])\s*\}", body, re.S
        ):
            patterns.append({pattern.group(1): json.loads(pattern.group(2))})
        assert patterns, f"No supported path condition found for {name}"
        rules.append(
            (
                name,
                {
                    "priority": int(re.search(r"priority\s*=\s*(\d+)", body).group(1)),
                    "condition": [{"path_pattern": patterns}],
                },
            )
        )
    rules.sort(key=lambda item: item[1]["priority"])
    assert len(rules) == 4
    routes = json.loads((ROOT / "infra/terraform/routing/routes.json").read_text())
    for _, rule in rules:
        for condition in rule["condition"]:
            for pattern in condition.get("path_pattern", []):
                assert (
                    len(pattern.get("values") or []) + len(pattern.get("regex_values") or []) <= 3
                )
    for key, value in routes.items():
        path = re.sub(r"\{[^}]+\}", "test-id", key.split(" ", 1)[1])
        matches = []
        for name, rule in rules:
            patterns = [p for c in rule["condition"] for p in c.get("path_pattern", [])]
            if any(
                any(fnmatch.fnmatchcase(path, v) for v in p.get("values") or [])
                or any(re.fullmatch(v, path) for v in p.get("regex_values") or [])
                for p in patterns
            ):
                matches.append(name)
        assert matches and matches[0] == value["service"], key


def test_public_route_boundary_and_authentication():
    routes = json.loads((ROOT / "infra/terraform/routing/routes.json").read_text())
    assert len(routes) == 29 and sum(v["public"] for v in routes.values()) == 3
    assert all(k.startswith("GET ") for k, v in routes.items() if v["public"])
    assert not any(
        "/mock-payment" in k or "/admin/mock-tickets/" in k or "/health" in k or "{proxy+" in k
        for k in routes
    )
    assert "POST /api/v1/payments/checkouts/{checkout_id}/complete" in routes
    assert "GET /api/v1/bookings/{booking_id}/tickets" in routes
    assert not routes["POST /api/v1/admin/visit-slots"]["public"]
    assert not routes["GET /api/v1/booking-policy"]["public"]
    assert not routes["GET /api/v1/visit-slots"]["public"]


def test_owner_guard_rejects_policy_or_baseline_tampering(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "routing_guard", ROOT / "infra/terraform/routing/verify_access.py"
    )
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    original = json.loads((ROOT / "infra/terraform/routing/operator-policy.json").read_text())
    original["Statement"][0]["Resource"] = "*"
    (tmp_path / "operator-policy.json").write_text(json.dumps(original))
    with pytest.raises(AssertionError, match="Unreviewed routing policy"):
        guard.verify(tmp_path, {"InlinePolicy": "{}"})
    with pytest.raises(AssertionError):
        guard.verify(ROOT / "infra/terraform/routing", {"InlinePolicy": "{}"})


def test_target_binding_has_no_public_service_or_credentials(tmp_path):
    values = {
        "vpcId": "vpc-00967ab06f35249ff",
        "targetGroups": {
            s: "arn:aws:elasticloadbalancing:ap-south-1:708919751353:"
            f"targetgroup/wl-demo-{s}/123abc"
            for s in ["catalog", "booking", "payment", "admission"]
        },
    }
    path = tmp_path / "values.json"
    path.write_text(json.dumps(values))
    local = ROOT / ".local/tools/helm/windows-amd64/helm.exe"
    helm = str(local) if local.exists() else shutil.which("helm")
    assert helm, "Install Helm before running chart checks"
    result = subprocess.run(
        [
            str(helm),
            "template",
            "wonderland-routing",
            str(ROOT / "deploy/helm/routing"),
            "--namespace",
            "wonderland",
            "--kube-version",
            "1.35.8-eks-b9510e3",
            "-f",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    docs = list(yaml.safe_load_all(result.stdout))
    assert len(docs) == 4 and all(
        d["kind"] == "TargetGroupBinding"
        and d["spec"]["targetType"] == "ip"
        and d["spec"]["serviceRef"]["port"] == 8000
        for d in docs
    )
    values["targetGroups"]["catalog"] = (
        "arn:aws:elasticloadbalancing:us-east-1:000000000000:targetgroup/unreviewed/123abc"
    )
    path.write_text(json.dumps(values))
    rejected = subprocess.run(
        [
            str(helm),
            "template",
            "wonderland-routing",
            str(ROOT / "deploy/helm/routing"),
            "--namespace",
            "wonderland",
            "--kube-version",
            "1.35.8-eks-b9510e3",
            "-f",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0 and "Unexpected target group ARN" in rejected.stderr
