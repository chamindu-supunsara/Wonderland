"""Read-only AWS permission review; never updates permissions or applies Terraform."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infra/terraform/foundation"))
from merge_operator_policy import CURRENT_SHA256, digest, merge  # noqa: E402


def main():
    session = boto3.Session(profile_name="wonderland-feasibility", region_name="ap-south-1")
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != "708919751353" or ":assumed-role/AWSReservedSSO_WonderlandFeasibility_" not in identity["Arn"]:
        raise SystemExit("Stop: use the expected non-root WonderlandFeasibility identity")
    iam = session.client("iam")
    role_name = identity["Arn"].split("/")[1]
    current = iam.get_role_policy(RoleName=role_name, PolicyName="AwsSSOInlinePolicy")["PolicyDocument"]
    attached = iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]
    if "arn:aws:iam::aws:policy/ReadOnlyAccess" not in {p["PolicyArn"] for p in attached}:
        raise SystemExit("Stop: expected AWS-managed ReadOnlyAccess is missing")
    proposal = json.loads((ROOT / "infra/terraform/foundation/operator-policy.json").read_text())
    merged = merge(proposal, current)
    encoded = json.dumps(merged, separators=(",", ":"))
    analyzer = session.client("accessanalyzer")
    findings = []
    request = {"policyType": "IDENTITY_POLICY", "policyDocument": encoded}
    while True:
        response = analyzer.validate_policy(**request)
        findings.extend(response["findings"])
        if not response.get("nextToken"):
            break
        request["nextToken"] = response["nextToken"]
    if findings:
        raise SystemExit("Stop: Access Analyzer findings need review: " + json.dumps(findings))
    plan_path = ROOT / ".local/deployment/foundation-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    mutations = [c for c in plan["resource_changes"] if c["change"]["actions"] != ["no-op"] and c["mode"] == "managed"]
    if len(mutations) != 56 or any(c["change"]["actions"] != ["create"] for c in mutations):
        raise SystemExit("Stop: saved foundation plan no longer has exactly 56 additions only")
    # Check live existence without reading secret values, credentials or billing APIs.
    cluster_exists = "wonderland-demo" in session.client("eks").list_clusters()["clusters"]
    db_exists = any(db["DBInstanceIdentifier"] == "wonderland-demo" for page in session.client("rds").get_paginator("describe_db_instances").paginate() for db in page["DBInstances"])
    if cluster_exists or db_exists:
        raise SystemExit("Stop: foundation resources already exist; inspect state and refresh the plan")
    costs = json.loads((ROOT / "docs/evidence/step10-foundation-costs.json").read_text())
    seven_day_model = round(sum(item["monthly_730h_usd"] for item in costs["line_items"]) * 168 / 730, 2)
    evidence = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "PREPARED_NOT_APPLIED" if digest(current) == CURRENT_SHA256 else "PERMISSIONS_PRESENT_INFRASTRUCTURE_NOT_APPLIED",
        "account": identity["Account"], "region": "ap-south-1", "role_name": role_name,
        "managed_read_policy": "arn:aws:iam::aws:policy/ReadOnlyAccess",
        "existing_inline_sha256": digest(current), "proposal_sha256": digest(proposal),
        "merged_inline_sha256": digest(merged), "merged_compact_bytes": len(encoded.encode()),
        "inline_limit_bytes": 10240, "new_statements": len(proposal["Statement"]),
        "access_analyzer_findings": findings,
        "foundation_plan": {"add": 56, "change": 0, "destroy": 0},
        "foundation_cluster_exists": cluster_exists, "foundation_database_exists": db_exists,
        "checkout": "mock", "requested_runtime_days": 7,
        "core_seven_day_model_usd": seven_day_model,
        "limitations": ["Policy validation is not a live deployment or proof of all runtime authorization", "Existing broad Mumbai EC2, ELB and API Gateway permissions are preserved", "New NAT/Elastic IP lifecycle permissions apply throughout Mumbai", "Repository and application-secret names use the wonderland-demo/ prefix", "RDS-generated secret creation/tagging uses the rds!db- prefix", "No new secret-value read or write APIs; CreateSecret can contain an initial value", "Runtime duration is guidance; no automatic cleanup or spending cap is scheduled"],
    }
    output = ROOT / "docs/evidence/step10-foundation-permissions.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    private_output = ROOT / ".local/deployment/foundation-merged-policy.json"
    private_output.write_text(encoded)
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
