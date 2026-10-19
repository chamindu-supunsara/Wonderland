"""Step09 operations. Uses temporary AWS CLI credentials; never exports credentials."""

import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local" / "feasibility"
ACCOUNT = "708919751353"
REGION = "ap-south-1"
STACK = "wonderland-step09-mock"
CHANGE = "step09-create"
TEMPLATE = ROOT / "infra/feasibility/cloudformation.json"


def run(args, *, input_text=None, timeout=60):
    result = subprocess.run(
        [str(x) for x in args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Command failed")
    return result.stdout


def aws(profile, *args):
    local = ROOT / ".local/tools/aws-cli/Amazon/AWSCLIV2/aws.exe"
    executable = str(local) if local.exists() else shutil.which("aws")
    if not executable:
        raise RuntimeError("AWS CLI is missing")
    raw = run(
        [
            executable,
            *args,
            "--profile",
            profile,
            "--region",
            REGION,
            "--output",
            "json",
            "--no-cli-pager",
        ]
    )
    return json.loads(raw) if raw.strip() else {}


def save(name, data):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def identity(profile, *, mutation=False):
    who = aws(profile, "sts", "get-caller-identity")
    if who["Account"] != ACCOUNT:
        raise RuntimeError(f"Wrong account: expected {ACCOUNT}")
    if mutation and who["Arn"].endswith(":root"):
        raise RuntimeError("Use a temporary non-root IAM/Identity Center session for deployment")
    return who


def operator_principal(profile, who):
    if ":iam::" in who["Arn"] and ":user/" in who["Arn"]:
        return who["Arn"]
    match = re.fullmatch(r"arn:aws:sts::\d+:assumed-role/([^/]+)/.+", who["Arn"])
    if not match:
        raise RuntimeError("Cannot resolve a persistent IAM principal for EKS access")
    # get-role preserves the full Identity Center role path; never use the STS session ARN.
    return aws(profile, "iam", "get-role", "--role-name", match[1])["Role"]["Arn"]


def check(profile):
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "account": ACCOUNT,
        "region": REGION,
        "checks": {},
        "deployment_permissions_verified": False,
    }
    try:
        who = identity(profile)
        report["identity"] = who
        report["non_root"] = not who["Arn"].endswith(":root")
    except RuntimeError as exc:
        report["authentication_error"] = str(exc)
        save("account-check.json", report)
        raise
    probes = {
        "availability_zones": ["ec2", "describe-availability-zones"],
        "eks_versions": ["eks", "describe-cluster-versions"],
        "eks_clusters": ["eks", "list-clusters"],
        "http_apis": ["apigatewayv2", "get-apis"],
        "vpc_links": ["apigatewayv2", "get-vpc-links"],
        "vpcs": ["ec2", "describe-vpcs"],
        "load_balancers": ["elbv2", "describe-load-balancers"],
        "repositories": ["ecr", "describe-repositories"],
        "ec2_quotas": ["service-quotas", "list-service-quotas", "--service-code", "ec2"],
        "eks_quotas": ["service-quotas", "list-service-quotas", "--service-code", "eks"],
        "vpc_quotas": ["service-quotas", "list-service-quotas", "--service-code", "vpc"],
        "alb_quotas": [
            "service-quotas",
            "list-service-quotas",
            "--service-code",
            "elasticloadbalancing",
        ],
        "gateway_quotas": ["service-quotas", "list-service-quotas", "--service-code", "apigateway"],
        "messaging_stack": [
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            "wonderland-events-dev",
        ],
        "cognito_pool": [
            "cognito-idp",
            "describe-user-pool",
            "--user-pool-id",
            "ap-south-1_aBuDlZ9RC",
        ],
    }
    for name, args in probes.items():
        try:
            report["checks"][name] = {"status": "READ_OK", "result": aws(profile, *args)}
        except RuntimeError as exc:
            report["checks"][name] = {"status": "UNVERIFIED", "error": str(exc)}
        save("account-check.json", report)
        print(f"{name}: {report['checks'][name]['status']}", flush=True)
    print(
        "Read-only evidence saved to .local/feasibility/account-check.json. "
        "Read access does not prove create/pass-role permissions."
    )


def plan(args):
    who = identity(args.profile, mutation=True)
    cidr = ipaddress.ip_network(args.operator_cidr, strict=True)
    if cidr.version != 4 or cidr.prefixlen != 32 or not cidr.network_address.is_global:
        raise RuntimeError("Provide your current public IPv4 address as a single /32")
    versions = aws(args.profile, "eks", "describe-cluster-versions")["clusterVersions"]
    if not any(
        v["clusterVersion"] == args.version and v["status"] == "STANDARD_SUPPORT" for v in versions
    ):
        raise RuntimeError("Requested EKS version is not currently in regional standard support")
    arn = operator_principal(args.profile, who)
    parameters = [
        {"ParameterKey": k, "ParameterValue": v}
        for k, v in {
            "OperatorArn": arn,
            "OperatorCidr": str(cidr),
            "KubernetesVersion": args.version,
        }.items()
    ]
    save("parameters.json", parameters)
    aws(
        args.profile, "cloudformation", "validate-template", "--template-body", f"file://{TEMPLATE}"
    )
    result = aws(
        args.profile,
        "cloudformation",
        "create-change-set",
        "--stack-name",
        STACK,
        "--change-set-name",
        CHANGE,
        "--change-set-type",
        "CREATE",
        "--template-body",
        f"file://{TEMPLATE}",
        "--capabilities",
        "CAPABILITY_IAM",
        "--parameters",
        f"file://{STATE / 'parameters.json'}",
        "--tags",
        "Key=Project,Value=Wonderland",
        "Key=Purpose,Value=Step09MOCK",
    )
    save("change-set.json", result)
    print("Change set submitted; no infrastructure executed. Run status to review it.")


def outputs(profile):
    stack = aws(profile, "cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    if stack["StackStatus"] != "CREATE_COMPLETE":
        raise RuntimeError(f"Stack is {stack['StackStatus']}; inspect status before proceeding")
    return {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}


def workload(image):
    labels = {"app": "mock-probe"}
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "wonderland-smoke"}},
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "mock-probe", "namespace": "wonderland-smoke"},
                "spec": {
                    "replicas": 2,
                    "selector": {"matchLabels": labels},
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "automountServiceAccountToken": False,
                            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001},
                            "containers": [
                                {
                                    "name": "probe",
                                    "image": image,
                                    "ports": [{"containerPort": 8000}],
                                    "resources": {
                                        "requests": {"cpu": "100m", "memory": "64Mi"},
                                        "limits": {"cpu": "500m", "memory": "256Mi"},
                                    },
                                    "securityContext": {
                                        "readOnlyRootFilesystem": True,
                                        "allowPrivilegeEscalation": False,
                                        "capabilities": {"drop": ["ALL"]},
                                    },
                                    "readinessProbe": {
                                        "httpGet": {"path": "/smoke/health", "port": 8000}
                                    },
                                    "livenessProbe": {
                                        "httpGet": {"path": "/smoke/health", "port": 8000}
                                    },
                                }
                            ],
                        },
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "mock-probe", "namespace": "wonderland-smoke"},
                "spec": {
                    "type": "NodePort",
                    "selector": labels,
                    "ports": [{"port": 80, "targetPort": 8000, "nodePort": 30080}],
                },
            },
        ],
    }


def kubectl(args, version):
    executable = ROOT / ".local/tools/kubectl.exe"
    tool = str(executable) if executable.exists() else shutil.which("kubectl")
    if not tool:
        raise RuntimeError("Install a matching kubectl client; see Step09 guide")
    client = json.loads(run([tool, "version", "--client", "-o", "json"]))["clientVersion"]
    minor = int(re.sub(r"\D", "", client["minor"]))
    if int(client["major"]) != 1 or abs(minor - int(version.split(".")[1])) > 1:
        raise RuntimeError("Installed kubectl is outside supported client/server version skew")
    return [tool, "--kubeconfig", str(STATE / "kubeconfig"), *args]


def publish(args):
    identity(args.profile, mutation=True)
    out = outputs(args.profile)
    version = aws(args.profile, "eks", "describe-cluster", "--name", out["ClusterName"])["cluster"][
        "version"
    ]
    kubectl([], version)  # Fail before building if the client is incompatible.
    tag = datetime.now(UTC).strftime("smoke-%Y%m%d%H%M%S")
    image = f"{out['RepositoryUri']}:{tag}"
    print(
        run(
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-f",
                "infra/feasibility/Dockerfile",
                "-t",
                image,
                ".",
            ],
            timeout=900,
        )
    )
    # Password is captured only in memory, supplied to stdin, never printed or saved.
    local = ROOT / ".local/tools/aws-cli/Amazon/AWSCLIV2/aws.exe"
    cli = str(local) if local.exists() else shutil.which("aws")
    password = run(
        [cli, "ecr", "get-login-password", "--profile", args.profile, "--region", REGION]
    )
    docker_config = str(STATE / "docker")
    print(
        run(
            [
                "docker",
                "--config",
                docker_config,
                "login",
                "--username",
                "AWS",
                "--password-stdin",
                out["RepositoryUri"].split("/")[0],
            ],
            input_text=password,
        )
    )
    print(run(["docker", "--config", docker_config, "push", image], timeout=900))
    repository = out["RepositoryUri"].split("/", 1)[1]
    digest = aws(
        args.profile,
        "ecr",
        "describe-images",
        "--repository-name",
        repository,
        "--image-ids",
        f"imageTag={tag}",
    )["imageDetails"][0]["imageDigest"]
    save("workload.json", workload(f"{out['RepositoryUri']}@{digest}"))
    print(
        run(
            [
                cli,
                "eks",
                "update-kubeconfig",
                "--name",
                out["ClusterName"],
                "--profile",
                args.profile,
                "--region",
                REGION,
                "--kubeconfig",
                str(STATE / "kubeconfig"),
            ]
        )
    )
    print(run(kubectl(["apply", "-f", str(STATE / "workload.json")], version)))
    print(
        run(
            kubectl(
                [
                    "-n",
                    "wonderland-smoke",
                    "rollout",
                    "status",
                    "deployment/mock-probe",
                    "--timeout=180s",
                ],
                version,
            ),
            timeout=200,
        )
    )
    nodes = json.loads(run(kubectl(["get", "nodes", "-o", "json"], version)))["items"]
    targets = [
        {"Id": node["spec"]["providerID"].rsplit("/", 1)[1], "Port": 30080} for node in nodes
    ]
    # This dedicated stack has exactly one managed node. Re-run publish after replacement.
    if len(targets) != 1:
        raise RuntimeError("Expected exactly one experimental node; inspect the cluster")
    save("targets.json", targets)
    aws(
        args.profile,
        "elbv2",
        "register-targets",
        "--target-group-arn",
        out["TargetGroupArn"],
        "--targets",
        f"file://{STATE / 'targets.json'}",
    )
    # Preserve exact billable child-resource IDs for verification after stack deletion.
    instances = aws(args.profile, "ec2", "describe-instances", "--instance-ids", targets[0]["Id"])
    volume_ids = [
        disk["Ebs"]["VolumeId"]
        for reservation in instances["Reservations"]
        for instance in reservation["Instances"]
        for disk in instance.get("BlockDeviceMappings", [])
        if "Ebs" in disk
    ]
    if not volume_ids:
        raise RuntimeError("Cannot capture the worker disk IDs for cleanup verification")
    volumes = aws(args.profile, "ec2", "describe-volumes", "--volume-ids", *volume_ids)
    group = aws(
        args.profile,
        "eks",
        "describe-nodegroup",
        "--cluster-name",
        out["ClusterName"],
        "--nodegroup-name",
        out["NodeGroupName"],
    )["nodegroup"]
    autoscaling = aws(
        args.profile,
        "autoscaling",
        "describe-auto-scaling-groups",
        "--auto-scaling-group-names",
        *[item["name"] for item in group["resources"]["autoScalingGroups"]],
    )
    save(
        "live-node-inventory.json",
        {
            "instances": instances,
            "volumes": volumes,
            "auto_scaling": autoscaling,
        },
    )
    print("Probe deployed. Wait for healthy targets using status, then run test.")


def test(profile):
    out = outputs(profile)
    endpoint = out["ApiEndpoint"]
    samples = []
    for _ in range(5):
        started = time.perf_counter()
        with urllib.request.urlopen(endpoint + "/smoke/health", timeout=15) as response:
            body = json.load(response)
            if response.status != 200 or body.get("mode") != "MOCK" or body.get("status") != "ok":
                raise RuntimeError("Unexpected probe response")
            samples.append(
                {"latency_ms": round((time.perf_counter() - started) * 1000, 2), "body": body}
            )
        time.sleep(1)
    try:
        urllib.request.urlopen(endpoint + "/api/v1/bookings", timeout=15)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError(f"Expected missing route 404; got {exc.code}") from exc
    else:
        raise RuntimeError("An application route is unexpectedly exposed")
    save(
        "cloud-test.json",
        {
            "tested_at": datetime.now(UTC).isoformat(),
            "endpoint": endpoint,
            "samples": samples,
            "missing_route": 404,
        },
    )
    print(json.dumps(samples, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["check", "plan", "status", "deploy", "publish", "test", "destroy"]
    )
    parser.add_argument("--profile", default="wonderland-feasibility")
    parser.add_argument("--operator-cidr")
    parser.add_argument("--version", default="1.35")
    parser.add_argument("--approve-billable-resources", action="store_true")
    parser.add_argument("--confirm-stack")
    args = parser.parse_args()
    os.environ.update(
        {
            "AWS_CONFIG_FILE": str(ROOT / ".local/aws/config"),
            "AWS_LOGIN_CACHE_DIRECTORY": str(ROOT / ".local/aws/login/cache"),
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_DEFAULT_REGION": REGION,
        }
    )
    local_cli_directory = ROOT / ".local/tools/aws-cli/Amazon/AWSCLIV2"
    if local_cli_directory.exists():
        os.environ["PATH"] = str(local_cli_directory) + os.pathsep + os.environ.get("PATH", "")
    if args.action == "check":
        check(args.profile)
        return
    identity(args.profile, mutation=args.action in {"plan", "deploy", "publish", "destroy"})
    if args.action == "plan":
        if not args.operator_cidr:
            parser.error("plan requires --operator-cidr YOUR_PUBLIC_IPV4/32")
        plan(args)
    elif args.action == "status":
        print(
            json.dumps(
                aws(args.profile, "cloudformation", "describe-stacks", "--stack-name", STACK),
                indent=2,
            )
        )
        print(
            json.dumps(
                aws(
                    args.profile,
                    "cloudformation",
                    "describe-stack-events",
                    "--stack-name",
                    STACK,
                    "--max-items",
                    "15",
                ),
                indent=2,
            )
        )
        # Change sets are relevant before deployment; target health afterwards.
        stack = aws(args.profile, "cloudformation", "describe-stacks", "--stack-name", STACK)[
            "Stacks"
        ][0]
        if stack["StackStatus"] == "REVIEW_IN_PROGRESS":
            print(
                json.dumps(
                    aws(
                        args.profile,
                        "cloudformation",
                        "describe-change-set",
                        "--stack-name",
                        STACK,
                        "--change-set-name",
                        CHANGE,
                    ),
                    indent=2,
                )
            )
        elif stack["StackStatus"] == "CREATE_COMPLETE":
            print(
                json.dumps(
                    aws(
                        args.profile,
                        "apigatewayv2",
                        "get-vpc-link",
                        "--vpc-link-id",
                        outputs(args.profile)["VpcLinkId"],
                    ),
                    indent=2,
                )
            )
            print(
                json.dumps(
                    aws(
                        args.profile,
                        "elbv2",
                        "describe-target-health",
                        "--target-group-arn",
                        outputs(args.profile)["TargetGroupArn"],
                    ),
                    indent=2,
                )
            )
    elif args.action == "deploy":
        if not args.approve_billable_resources:
            parser.error(
                "Review costs/change set first; deploy requires --approve-billable-resources"
            )
        aws(
            args.profile,
            "cloudformation",
            "execute-change-set",
            "--stack-name",
            STACK,
            "--change-set-name",
            CHANGE,
        )
        print(
            "Deployment started. Run status periodically; billing starts as resources are created."
        )
    elif args.action == "publish":
        publish(args)
    elif args.action == "test":
        test(args.profile)
    elif args.action == "destroy":
        if args.confirm_stack != STACK:
            parser.error(f"destroy requires --confirm-stack {STACK}")
        stack = aws(args.profile, "cloudformation", "describe-stacks", "--stack-name", STACK)[
            "Stacks"
        ][0]
        tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
        if tags.get("Purpose") != "Step09MOCK":
            raise RuntimeError("Refusing deletion: experiment ownership tag is missing")
        save("before-cleanup.json", stack)
        save(
            "cleanup-resources.json",
            aws(args.profile, "cloudformation", "describe-stack-resources", "--stack-name", STACK),
        )
        aws(args.profile, "cloudformation", "delete-stack", "--stack-name", STACK)
        print(
            "Deletion started. Verify DELETE_COMPLETE / stack absent and resource removal in AWS."
        )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
