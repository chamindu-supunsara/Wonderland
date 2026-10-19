import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_metabase_is_private_hardened_and_uses_only_metadata_secret():
    local = ROOT / ".local/tools/helm/windows-amd64/helm.exe"
    helm = str(local) if local.exists() else shutil.which("helm")
    assert helm, "Install Helm before running chart checks"
    result = subprocess.run(
        [
            helm,
            "template",
            "wonderland-metabase",
            str(ROOT / "deploy/helm/metabase"),
            "--namespace",
            "wonderland",
            "--kube-version",
            "1.35.8-eks-b9510e3",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    docs = list(yaml.safe_load_all(result.stdout))
    assert {d["kind"] for d in docs} == {"ServiceAccount", "Deployment", "Service"}
    service = next(d for d in docs if d["kind"] == "Service")
    assert service["spec"]["type"] == "ClusterIP" and not service["spec"].get("externalIPs")
    deployment = next(d for d in docs if d["kind"] == "Deployment")
    assert (
        deployment["spec"]["replicas"] == 1 and deployment["spec"]["strategy"]["type"] == "Recreate"
    )
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert pod["automountServiceAccountToken"] is False and pod["securityContext"]["runAsNonRoot"]
    assert (
        container["securityContext"]["readOnlyRootFilesystem"]
        and not container["securityContext"]["allowPrivilegeEscalation"]
    )
    assert container["envFrom"] == [{"secretRef": {"name": "wonderland-metabase-app"}}]
    env = {e["name"]: e["value"] for e in container["env"]}
    assert env["MB_ENABLE_PUBLIC_SHARING"] == env["MB_ENABLE_EMBEDDING"] == "false"
    assert env["MB_DB_TYPE"] == "postgres" and env["MB_REPORT_TIMEZONE"] == "Asia/Colombo"
    assert "@sha256:" in container["image"]
    assert container["resources"]["requests"]["memory"] == "1536Mi"


def test_bootstrap_role_cannot_write_master_or_read_other_service_secrets():
    import json

    template = json.loads((ROOT / "infra/bi/bootstrap-access.json").read_text())
    role = template["Resources"]["BootstrapRole"]["Properties"]
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    assert (
        statements[0]["Action"] == "secretsmanager:GetSecretValue"
        and ":secret:rds!db-" in statements[0]["Resource"]
    )
    assert len(statements[1]["Resource"]) == 2 and all(
        "/metabase-" in r and r.endswith("-??????") for r in statements[1]["Resource"]
    )
    assert set(statements[1]["Action"]) == {
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
    }
    trust = role["AssumeRolePolicyDocument"]["Statement"][0]
    assert (
        trust["Condition"]["StringEquals"]["aws:RequestTag/kubernetes-service-account"]
        == "bi-bootstrap"
    )
