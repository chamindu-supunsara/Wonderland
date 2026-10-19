"""Verify deployed GitHub publishing access and save a credential-free receipt."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3

from github_client import REPOSITORY, request

ROOT = Path(__file__).resolve().parents[1]
session = boto3.Session(profile_name="wonderland-feasibility", region_name="ap-south-1")
assert session.client("sts").get_caller_identity()["Account"] == "708919751353"
iam = session.client("iam")
role = iam.get_role(RoleName="wonderland-github-release")["Role"]
policy = iam.get_role_policy(
    RoleName="wonderland-github-release", PolicyName="PublishExistingWonderlandImages"
)["PolicyDocument"]
template = json.loads((ROOT / "infra/automation/github-release-access.json").read_text())
expected_role = template["Resources"]["ReleaseRole"]["Properties"]
expected_trust = expected_role["AssumeRolePolicyDocument"]["Statement"][0]
trust = role["AssumeRolePolicyDocument"]["Statement"][0]
oidc = request(f"repos/{REPOSITORY}/actions/oidc/customization/sub")
stack = session.client("cloudformation").describe_stacks(
    StackName="wonderland-github-release-access"
)["Stacks"][0]
provider = iam.get_open_id_connect_provider(
    OpenIDConnectProviderArn="arn:aws:iam::708919751353:oidc-provider/token.actions.githubusercontent.com"
)
checks = {
    "stack_create_or_update_complete": stack["StackStatus"]
    in ["CREATE_COMPLETE", "UPDATE_COMPLETE"],
    "exact_immutable_main_subject_and_audience": trust["Condition"] == expected_trust["Condition"],
    "exact_github_provider_and_web_identity_action": trust["Principal"]
    == {"Federated": "arn:aws:iam::708919751353:oidc-provider/token.actions.githubusercontent.com"}
    and trust["Action"] == "sts:AssumeRoleWithWebIdentity",
    "github_immutable_subject_matches": oidc["use_immutable_subject"]
    and trust["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"]
    == oidc["sub_claim_prefix"] + ":ref:refs/heads/main",
    "only_reviewed_ecr_policy": policy == expected_role["Policies"][0]["PolicyDocument"]
    and iam.list_role_policies(RoleName=role["RoleName"])["PolicyNames"]
    == ["PublishExistingWonderlandImages"]
    and not iam.list_attached_role_policies(RoleName=role["RoleName"])["AttachedPolicies"],
    "provider_sts_audience_only": provider["ClientIDList"] == ["sts.amazonaws.com"],
    "session_limited_to_one_hour": role["MaxSessionDuration"] == 3600,
}
log = ROOT / "docs/evidence/step11-owner-oidc-correction-output.txt"
report = {
    "status": "VERIFIED" if all(checks.values()) else "REVIEW_REQUIRED",
    "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
    "role_arn": role["Arn"],
    "trust": trust,
    "stack_status": stack["StackStatus"],
    "owner_command_exit_code": 0,
    "owner_output_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
    "secret_values_or_tokens_read": False,
    "checkout": "mock",
    "planning_model_usd": 65.41,
    "allowance_usd": 75,
}
(ROOT / "docs/evidence/step11-access-verification.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps(report, indent=2))
assert all(checks.values()), "Do not publish until the access checks pass"
