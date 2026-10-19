"""Render the chart locally; never use a Kubernetes cluster or AWS credentials."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/tools/helm/windows-amd64/helm.exe"
HELM = str(LOCAL) if LOCAL.exists() else shutil.which("helm")
pytestmark = pytest.mark.skipif(not HELM, reason="Helm is required; run the Step 10 tool setup")
CHART = ROOT / "deploy/helm/wonderland"
FIXTURE = ROOT / "deploy/helm/tests/render-values.yaml"


def render(*options, fixture=True):
    return subprocess.run(
        [
            HELM,
            "template",
            "wonderland",
            str(CHART),
            "--namespace",
            "wonderland",
            "--kube-version",
            "1.35.0",
            *(["-f", str(FIXTURE)] if fixture else []),
            *options,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_no_workloads_without_explicit_enable():
    result = render(fixture=False)
    assert result.returncode == 0, result.stderr
    assert not list(yaml.safe_load_all(result.stdout))


def test_isolated_workloads_and_mock_configuration():
    result = render()
    assert result.returncode == 0, result.stderr
    documents = list(yaml.safe_load_all(result.stdout))
    deployments = [d for d in documents if d["kind"] == "Deployment"]
    assert len(deployments) == 11  # Four APIs and seven independently supervised workers.
    for item in deployments:
        pod = item["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"]["runAsNonRoot"] is True
        container = pod["containers"][0]
        assert "@sha256:" in container["image"]
        assert container["securityContext"]["readOnlyRootFilesystem"] is True
        assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
        assert container["resources"]["requests"] and container["resources"]["limits"]
    assert all(d["spec"]["type"] == "ClusterIP" for d in documents if d["kind"] == "Service")
    assert not any(d["kind"] in {"Secret", "Ingress"} for d in documents)
    config = next(d for d in documents if d["kind"] == "ConfigMap")["data"]
    assert config["MOCK_PAYMENTS_ENABLED"] == "true"
    assert config["MOCK_ADMISSION_ENABLED"] == "true"
    assert json.loads(config["CORS_ORIGINS"]) == ["https://wonderland.example.invalid"]
    assert "DATABASE_URL" not in config


@pytest.mark.parametrize(
    ("override", "expected_error"),
    [
        ("images.catalog=example.invalid/catalog:latest", "immutable"),
        ("frontendOrigin=http://example.invalid", "frontendOrigin"),
        ("apiReplicas=1", "apiReplicas"),
        ("workers.catalog-publisher.env.AWS_ACCESS_KEY_ID=unsafe", "AWS_ACCESS_KEY_ID"),
    ],
)
def test_reject_unsafe_or_incomplete_deployment_configuration(override, expected_error):
    result = render("--set", override)
    assert result.returncode != 0
    assert expected_error in result.stderr


def test_private_projection_rollout_has_no_browser_origin_and_worker_progress_probes():
    result = render("--set", "frontendOrigin=", "--set", "pricingMode=projection")
    assert result.returncode == 0, result.stderr
    documents = list(yaml.safe_load_all(result.stdout))
    config = next(d for d in documents if d["kind"] == "ConfigMap")["data"]
    assert json.loads(config["CORS_ORIGINS"]) == []
    assert config["PRICING_MODE"] == "projection"
    for item in [d for d in documents if d["kind"] == "Deployment"]:
        pod = item["spec"]["template"]
        assert pod["metadata"]["annotations"]["checksum/runtime"]
        if pod["metadata"]["labels"]["component"] == "worker":
            assert item["spec"]["strategy"]["type"] == "Recreate"
            for probe in ["startupProbe", "readinessProbe", "livenessProbe"]:
                assert pod["spec"]["containers"][0][probe]["exec"]["command"] == [
                    "python",
                    "-m",
                    "wonderland_events.health",
                ]
