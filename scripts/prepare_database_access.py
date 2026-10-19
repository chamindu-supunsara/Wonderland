"""Prepare exact, reviewable temporary bootstrap access from foundation outputs; no AWS calls."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main():
    output = {key: value["value"] for key, value in json.loads((ROOT / ".local/deployment/foundation-outputs.json").read_text(encoding="utf-8-sig")).items()}
    path = ROOT / "infra/database"
    path.mkdir(exist_ok=True)
    policy = {"Version": "2012-10-17", "Statement": [{"Sid": "DatabaseBootstrapImagePush", "Effect": "Allow",
        "Action": ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage"],
        "Resource": "arn:aws:ecr:ap-south-1:708919751353:repository/wonderland-demo/catalog"}]}
    (path / "operator-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "pods.eks.amazonaws.com"},
        "Action": ["sts:AssumeRole", "sts:TagSession"], "Condition": {"StringEquals": {
            "aws:RequestTag/kubernetes-namespace": "wonderland-bootstrap", "aws:RequestTag/kubernetes-service-account": "db-bootstrap",
            "aws:RequestTag/eks-cluster-arn": "arn:aws:eks:ap-south-1:708919751353:cluster/wonderland-demo"}}}]}
    access = {"Version": "2012-10-17", "Statement": [
        {"Sid": "ReadOnlyThisMaster", "Effect": "Allow", "Action": "secretsmanager:GetSecretValue", "Resource": output["database_master_secret_arn"]},
        {"Sid": "OnlyFiveServiceCredentials", "Effect": "Allow", "Action": ["secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"], "Resource": list(output["service_secret_arns"].values())}]}
    template = {"AWSTemplateFormatVersion": "2010-09-09", "Description": "Temporary Step10B private database bootstrap identity. No database or secret deletion resources.", "Resources": {
        "BootstrapRole": {"Type": "AWS::IAM::Role", "Properties": {"RoleName": "wonderland-demo-db-bootstrap", "MaxSessionDuration": 3600,
            "AssumeRolePolicyDocument": trust, "Policies": [{"PolicyName": "OnlyDatabaseBootstrapSecrets", "PolicyDocument": access}],
            "Tags": [{"Key": "Project", "Value": "Wonderland"}, {"Key": "Environment", "Value": "demo"}, {"Key": "Purpose", "Value": "temporary-db-bootstrap"}]}},
        "PodIdentity": {"Type": "AWS::EKS::PodIdentityAssociation", "Properties": {"ClusterName": "wonderland-demo", "Namespace": "wonderland-bootstrap", "ServiceAccount": "db-bootstrap", "RoleArn": {"Fn::GetAtt": ["BootstrapRole", "Arn"]}}}}}
    (path / "bootstrap-access.json").write_text(json.dumps(template, indent=2) + "\n")
    base = json.loads((ROOT / ".local/deployment/foundation-merged-policy.json").read_text())
    if any(s.get("Sid") == "DatabaseBootstrapImagePush" for s in base["Statement"]):
        base["Statement"] = [s for s in base["Statement"] if s.get("Sid") != "DatabaseBootstrapImagePush"]
    expected_base = "1cb5017593ad6b19334967a11b0f843c814578fc4ab5fd5ac480106c4c6e91c9"
    if hashlib.sha256(canonical(base).encode()).hexdigest() != expected_base:
        raise SystemExit("Baseline differs from reviewed foundation policy")
    merged = {**base, "Statement": base["Statement"] + policy["Statement"]}
    compact = json.dumps(merged, separators=(",", ":"))
    if len(compact.encode()) > 10240:
        raise SystemExit("Inline quota exceeded; do not truncate existing policy")
    (ROOT / ".local/deployment/database-merged-policy.json").write_text(compact)
    review = {"status": "PREPARED_NOT_APPLIED", "stack": "wonderland-db-bootstrap-access", "resources": ["temporary IAM role", "temporary Pod Identity association"],
              "operator_change": "ECR upload only for wonderland-demo/catalog; no operator secret-value access", "merged_inline_bytes": len(compact.encode()),
              "baseline_sha256": expected_base, "policy_sha256": hashlib.sha256(canonical(policy).encode()).hexdigest(),
              "template_sha256": hashlib.sha256(canonical(template).encode()).hexdigest(),
              "additional_rds_ec2_nat_instances": 0, "checkout": "mock"}
    (ROOT / "docs/evidence/step10b-access-review.json").write_text(json.dumps(review, indent=2) + "\n")
    print(json.dumps(review, indent=2))


if __name__ == "__main__":
    main()
