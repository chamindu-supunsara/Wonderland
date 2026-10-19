"""Read-only Mumbai quota/usage/version checks for the reviewed demo foundation."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
REGION = "ap-south-1"


def main():
    session = boto3.Session(profile_name="wonderland-feasibility", region_name=REGION)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != "708919751353" or ":assumed-role/AWSReservedSSO_WonderlandFeasibility_" not in identity["Arn"]:
        raise SystemExit("Stop: use the reviewed non-root deployment profile/account")
    clients = {name: session.client(name) for name in ["ec2", "eks", "rds", "iam", "service-quotas"]}
    raw = {}
    rows = []

    def read(service, operation, key, **kwargs):
        client = clients[service]
        if client.can_paginate(operation):
            values = [item for page in client.get_paginator(operation).paginate(**kwargs) for item in page[key]]
        else:
            values = getattr(client, operation)(**kwargs)[key]
        raw[f"{service}.{operation}"] = values
        return values

    def row(name, limit, used, additional, unit="count", scope="Mumbai"):
        projected = used + additional
        rows.append({"name": name, "scope": scope, "unit": unit, "limit": limit,
                     "current_usage": used, "planned_addition": additional,
                     "projected_usage": projected, "remaining_after": limit - projected,
                     "status": "PASS" if projected <= limit else "BLOCKED"})

    quotas = {}
    for service in ["ec2", "vpc", "eks", "ebs"]:
        entries = read("service-quotas", "list_service_quotas", "Quotas", ServiceCode=service)
        # Keep each service snapshot separately; read() otherwise uses the same operation key.
        raw[f"quotas.{service}"] = entries
        quotas.update({entry["QuotaCode"]: entry for entry in entries})
        print(f"Read {service} applied quotas.", flush=True)

    def limit(code):
        if code not in quotas:
            raise RuntimeError(f"Applied quota {code} unavailable; do not substitute an assumed default")
        return quotas[code]["Value"]

    azs = read("ec2", "describe_availability_zones", "AvailabilityZones", Filters=[{"Name": "state", "Values": ["available"]}])
    planned_azs = sorted(z["ZoneName"] for z in azs if z.get("ZoneType", "availability-zone") == "availability-zone")[:2]
    if len(planned_azs) != 2:
        raise RuntimeError("Two available standard Availability Zones are required")
    reservations = read("ec2", "describe_instances", "Reservations", Filters=[{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "shutting-down"]}])
    instances = [instance for reservation in reservations for instance in reservation["Instances"]]
    instance_types = sorted({instance["InstanceType"] for instance in instances} | {"t3.medium"})
    types = read("ec2", "describe_instance_types", "InstanceTypes", InstanceTypes=instance_types)
    cpu = {item["InstanceType"]: item["VCpuInfo"]["DefaultVCpus"] for item in types}
    standard = [instance for instance in instances if instance.get("InstanceLifecycle", "on-demand") == "on-demand" and re.match(r"^[acdhimrtz]\d", instance["InstanceType"])]
    used_cpu = sum(cpu[instance["InstanceType"]] for instance in standard)
    # Stopping/shutting-down instances are conservatively included until they finish.
    row("Standard On-Demand vCPUs", limit("L-1216C47A"), used_cpu, 2 * cpu["t3.medium"], "vCPU")
    addresses = read("ec2", "describe_addresses", "Addresses")
    row("EC2-VPC Elastic IPs", limit("L-0263D0A3"), len(addresses), 1)
    vpcs = read("ec2", "describe_vpcs", "Vpcs")
    row("VPCs", limit("L-F678F1CE"), len(vpcs), 1)
    gateways = read("ec2", "describe_internet_gateways", "InternetGateways")
    row("Internet gateways", limit("L-A4707A72"), len(gateways), 1)
    subnets = read("ec2", "describe_subnets", "Subnets")
    subnet_az = {subnet["SubnetId"]: subnet["AvailabilityZone"] for subnet in subnets}
    nats = read("ec2", "describe_nat_gateways", "NatGateways")
    occupied_nat = [nat for nat in nats if nat["State"] in {"pending", "available", "deleting"}]
    unknown_nat_zones = [nat["NatGatewayId"] for nat in occupied_nat if not nat.get("SubnetId") or nat["SubnetId"] not in subnet_az]
    if unknown_nat_zones:
        raise RuntimeError("NAT gateways with unresolved zonal usage require manual review")
    used_nat = sum(subnet_az[nat["SubnetId"]] == planned_azs[0] for nat in occupied_nat)
    row("NAT gateways in planned NAT zone", limit("L-FE5A380F"), used_nat, 1, scope=planned_azs[0])
    # A newly created VPC already receives a main route table and default security group.
    row("Subnets in new VPC", limit("L-407747CB"), 0, 6, scope="new wonderland-demo VPC")
    row("Route tables in new VPC", limit("L-589F43AA"), 0, 4, scope="new VPC, including automatic main table")
    clusters = read("eks", "list_clusters", "clusters")
    row("EKS clusters", limit("L-1194D53C"), len(clusters), 1)
    row("Managed node groups", limit("L-6D54EA21"), 0, 1, scope="new wonderland-demo cluster")
    row("Nodes in managed node group", limit("L-BD136A63"), 0, 2, scope="new application node group")
    volumes = read("ec2", "describe_volumes", "Volumes", Filters=[{"Name": "volume-type", "Values": ["gp3"]}])
    row("gp3 EBS storage", limit("L-7A658B76"), sum(v["Size"] for v in volumes) / 1024, 40 / 1024, "TiB")
    rds_limits = read("rds", "describe_account_attributes", "AccountQuotas")
    for name, addition in [("DBInstances", 1), ("DBSubnetGroups", 1), ("DBParameterGroups", 1), ("AllocatedStorage", 40), ("ManualSnapshots", 1)]:
        quota = next(q for q in rds_limits if q["AccountQuotaName"] == name)
        row(f"RDS {name}", quota["Max"], quota["Used"], addition, "GiB" if name == "AllocatedStorage" else "count")
    iam = clients["iam"].get_account_summary()["SummaryMap"]
    raw["iam.summary"] = iam
    row("IAM roles", iam["RolesQuota"], iam["Roles"], 2 + 1, scope="account; includes optional new RDS service-linked role")

    versions = read("eks", "describe_cluster_versions", "clusterVersions", clusterVersions=["1.35"])
    version = next((v for v in versions if v["clusterVersion"] == "1.35"), None)
    support_ok = bool(version and version["status"] == "STANDARD_SUPPORT")
    offerings = read("ec2", "describe_instance_type_offerings", "InstanceTypeOfferings", LocationType="availability-zone", Filters=[{"Name": "instance-type", "Values": ["t3.medium"]}])
    offered_azs = {entry["Location"] for entry in offerings}
    options = read("rds", "describe_orderable_db_instance_options", "OrderableDBInstanceOptions", Engine="postgres", DBInstanceClass="db.t4g.small", Vpc=True)
    compatible = [o for o in options if o["EngineVersion"].startswith("16.") and o["StorageType"] == "gp3" and o.get("SupportsStorageEncryption") and set(planned_azs).issubset({z["Name"] for z in o["AvailabilityZones"]})]
    dbs = read("rds", "describe_db_instances", "DBInstances")
    target_absent = "wonderland-demo" not in clusters and not any(db["DBInstanceIdentifier"] == "wonderland-demo" for db in dbs) and not any(any(t["Key"] == "Name" and t["Value"] == "wonderland-demo" for t in vpc.get("Tags", [])) for vpc in vpcs)
    checks = {"eks_1_35_standard_support": support_ok, "worker_type_offered_in_both_zones": set(planned_azs).issubset(offered_azs), "encrypted_postgres16_small_gp3_orderable_in_both_zones": bool(compatible), "target_foundation_absent": target_absent}
    passed = all(row["status"] == "PASS" for row in rows) and all(checks.values())
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "account": identity["Account"], "region": REGION,
              "status": "CHECKED_NO_DETECTED_QUOTA_BLOCKER" if passed else "REVIEW_REQUIRED", "profile": "wonderland-feasibility", "planned_zones": planned_azs,
              "quota_checks": rows, "availability_checks": checks,
              "eks_version": {key: version[key] for key in ["clusterVersion", "status", "releaseDate", "endOfStandardSupportDate", "endOfExtendedSupportDate", "kubernetesPatchVersion"] if version and key in version},
              "orderable_postgres16_versions": sorted({o["EngineVersion"] for o in compatible}, key=lambda v: tuple(map(int, v.split(".")))),
              "applied_standard_vcpu_quota": limit("L-1216C47A"), "current_standard_vcpu_usage": used_cpu,
              "worker_vcpus": 4, "quota_changes_requested": False, "terraform_applied": False, "checkout": "mock",
              "limitations": ["Point-in-time inventory; quotas are not reservations or a capacity guarantee", "Provider default main route table and security group are additional AWS objects outside the 56 Terraform additions", "Initial resource quotas checked; not all per-resource or later platform quotas are covered", "Storage account check reserves RDS maximum 40 GiB; worker storage assumes initial 2 nodes", "Managed-node upgrades can surge beyond the fixed desired worker count; review their quota/cost plan separately", "No deployment, quota increase, budget, spending cap or automatic cleanup scheduled"]}
    (ROOT / ".local/deployment/foundation-readiness-raw.json").write_text(json.dumps(raw, indent=2, default=str) + "\n")
    (ROOT / "docs/evidence/step10-foundation-readiness.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str), flush=True)
    if not passed:
        raise SystemExit("Readiness needs review; do not apply")


if __name__ == "__main__":
    main()
