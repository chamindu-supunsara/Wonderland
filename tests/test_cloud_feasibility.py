"""Cloud boundary and deployment safety checks; do not contact AWS or mutate Docker."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_exposes_only_mock_health():
    client = TestClient(load("infra/feasibility/app/main.py").app)
    assert client.get("/smoke/health").json()["mode"] == "MOCK"
    for route in ["/docs", "/openapi.json", "/api/v1/bookings", "/admin"]:
        assert client.get(route).status_code == 404
    assert client.post("/smoke/health").status_code == 405


@pytest.mark.parametrize(
    "who",
    [
        {"Account": "000000000000", "Arn": "arn:aws:iam::000000000000:user/test"},
        {"Account": "708919751353", "Arn": "arn:aws:iam::708919751353:root"},
    ],
)
def test_mutations_reject_wrong_account_and_root(monkeypatch, who):
    module = load("scripts/cloud_feasibility.py")
    monkeypatch.setattr(module, "aws", lambda *args: who)
    with pytest.raises(RuntimeError):
        module.identity("example", mutation=True)


def test_sso_principal_preserves_iam_role_path(monkeypatch):
    module = load("scripts/cloud_feasibility.py")
    arn = (
        "arn:aws:iam::708919751353:role/aws-reserved/"
        "sso.amazonaws.com/ap-south-1/AWSReservedSSO_Test_123"
    )
    monkeypatch.setattr(module, "aws", lambda *args: {"Role": {"Arn": arn}})
    result = module.operator_principal(
        "example", {"Arn": "arn:aws:sts::708919751353:assumed-role/AWSReservedSSO_Test_123/session"}
    )
    assert result == arn


def test_cloud_boundary_and_bounded_resources():
    template = load("infra/feasibility/template.py").build_template()
    assert template == json.loads((ROOT / "infra/feasibility/cloudformation.json").read_text())
    resources = template["Resources"]
    props = lambda key: resources[key]["Properties"]  # noqa: E731
    assert props("Cluster")["UpgradePolicy"]["SupportType"] == "STANDARD"
    assert props("Cluster")["ResourcesVpcConfig"]["PublicAccessCidrs"] == [{"Ref": "OperatorCidr"}]
    assert props("Nodes")["ScalingConfig"]["MaxSize"] == 1
    assert props("LoadBalancer")["Scheme"] == "internal"
    assert props("Route")["RouteKey"] == "GET /smoke/health"
    assert props("Integration")["ConnectionType"] == "VPC_LINK"
    assert props("Integration")["RequestParameters"]["overwrite:path"] == "$request.path"
    assert not any(
        r["Type"] in {"AWS::EC2::NatGateway", "AWS::RDS::DBInstance"} for r in resources.values()
    )
    assert props("AlbToNodePort")["SourceSecurityGroupId"] == {"Ref": "AlbSg"}


def test_workload_has_no_aws_token_or_app_secrets():
    manifest = load("scripts/cloud_feasibility.py").workload("example@sha256:123")
    pod = manifest["items"][1]["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert "env" not in pod["containers"][0]
    assert pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"] is True


@pytest.mark.parametrize("action", ["deploy", "destroy"])
def test_destructive_or_billable_actions_require_explicit_flags(monkeypatch, action):
    module = load("scripts/cloud_feasibility.py")
    calls = []

    def fake_aws(profile, *args):
        calls.append(args)
        assert args == ("sts", "get-caller-identity")
        return {"Account": "708919751353", "Arn": "arn:aws:iam::708919751353:user/developer"}

    monkeypatch.setattr(module, "aws", fake_aws)
    monkeypatch.setattr(sys, "argv", ["cloud_feasibility.py", action])
    monkeypatch.setattr(os, "environ", dict(os.environ))
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
    assert len(calls) == 1
