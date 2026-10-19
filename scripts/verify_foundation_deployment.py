"""Verify deployed foundation using read-only AWS calls and saved kubectl results."""

import json
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]


def main():
    session = boto3.Session(profile_name="wonderland-feasibility", region_name="ap-south-1")
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != "708919751353" or ":assumed-role/AWSReservedSSO_WonderlandFeasibility_" not in identity["Arn"]:
        raise SystemExit("Stop: verification requires the expected non-root deployment identity")
    local = ROOT / ".local/deployment"
    outputs = {key: value["value"] for key, value in json.loads((local / "foundation-outputs.json").read_text(encoding="utf-8-sig")).items()}
    eks, ec2, rds = [session.client(name) for name in ["eks", "ec2", "rds"]]
    cluster = eks.describe_cluster(name="wonderland-demo")["cluster"]
    nodegroup = eks.describe_nodegroup(clusterName="wonderland-demo", nodegroupName="application")["nodegroup"]
    addon = eks.describe_addon(clusterName="wonderland-demo", addonName="eks-pod-identity-agent")["addon"]
    database = rds.describe_db_instances(DBInstanceIdentifier="wonderland-demo")["DBInstances"][0]
    subnets = ec2.describe_subnets(SubnetIds=outputs["private_compute_subnets"])["Subnets"]
    nat = [n for page in ec2.get_paginator("describe_nat_gateways").paginate(Filter=[{"Name": "vpc-id", "Values": [outputs["vpc_id"]]}]) for n in page["NatGateways"] if n["State"] != "deleted"]
    asg_names = [group["name"] for group in nodegroup["resources"]["autoScalingGroups"]]
    asgs = session.client("autoscaling").describe_auto_scaling_groups(AutoScalingGroupNames=asg_names)["AutoScalingGroups"]
    instance_ids = [instance["InstanceId"] for group in asgs for instance in group["Instances"]]
    instances = [instance for reservation in ec2.describe_instances(InstanceIds=instance_ids)["Reservations"] for instance in reservation["Instances"]] if instance_ids else []
    volume_ids = [mapping["Ebs"]["VolumeId"] for instance in instances for mapping in instance.get("BlockDeviceMappings", []) if "Ebs" in mapping]
    volumes = ec2.describe_volumes(VolumeIds=volume_ids)["Volumes"] if volume_ids else []
    repositories = session.client("ecr").describe_repositories(repositoryNames=[f"wonderland-demo/{service}" for service in ["catalog", "booking", "payment", "admission", "analytics"]])["repositories"]
    secrets = [session.client("secretsmanager").describe_secret(SecretId=arn) for arn in outputs["service_secret_arns"].values()]
    parameter_name = database["DBParameterGroups"][0]["DBParameterGroupName"]
    parameters = [parameter for page in rds.get_paginator("describe_db_parameters").paginate(DBParameterGroupName=parameter_name) for parameter in page["Parameters"]]
    variables = json.loads((ROOT / "infra/terraform/foundation/terraform.tfvars.json").read_text(encoding="utf-8-sig"))
    policies = eks.list_associated_access_policies(clusterName="wonderland-demo", principalArn=variables["operator_arn"])["associatedAccessPolicies"]
    access = cluster["resourcesVpcConfig"]
    log_groups = session.client("logs").describe_log_groups(logGroupNamePrefix="/aws/eks/wonderland-demo/cluster")["logGroups"]
    node_data = json.loads((local / "foundation-nodes.json").read_text(encoding="utf-8-sig"))["items"]
    pod_data = json.loads((local / "foundation-system-pods.json").read_text(encoding="utf-8-sig"))["items"]
    healthy_pods = all(p["status"].get("phase") == "Succeeded" or (p["status"].get("phase") == "Running" and p["status"].get("containerStatuses") and all(c["ready"] for c in p["status"]["containerStatuses"])) for p in pod_data)
    checks = {
        "cluster_active": cluster["status"] == "ACTIVE",
        "cluster_version_standard_1_35": cluster["version"] == "1.35" and cluster["upgradePolicy"]["supportType"] == "STANDARD",
        "cluster_private_endpoint_and_operator_only_public_access": access["endpointPrivateAccess"] and access["endpointPublicAccess"] and access["publicAccessCidrs"] == [variables["operator_cidr"]],
        "explicit_operator_cluster_admin": any(p["policyArn"].endswith("/AmazonEKSClusterAdminPolicy") and p["accessScope"]["type"] == "cluster" for p in policies),
        "nodegroup_active_without_health_issues": nodegroup["status"] == "ACTIVE" and not nodegroup.get("health", {}).get("issues"),
        "nodegroup_fixed_two_workers": nodegroup["scalingConfig"] == {"minSize": 2, "maxSize": 2, "desiredSize": 2},
        "two_private_running_t3_medium_workers": len(instances) == 2 and all(i["InstanceType"] == "t3.medium" and i["State"]["Name"] == "running" and not i.get("PublicIpAddress") and i["MetadataOptions"]["HttpTokens"] == "required" for i in instances),
        "compute_subnets_no_auto_public_ips": len(subnets) == 2 and all(not s["MapPublicIpOnLaunch"] for s in subnets),
        "worker_disks_encrypted_gp3_20gib": len(volumes) == 2 and all(v["Encrypted"] and v["VolumeType"] == "gp3" and v["Size"] == 20 for v in volumes),
        "two_kubernetes_nodes_ready": len(node_data) == 2 and all(any(c["type"] == "Ready" and c["status"] == "True" for c in node["status"]["conditions"]) for node in node_data),
        "system_pods_healthy": bool(pod_data) and healthy_pods,
        "pod_identity_agent_active": addon["status"] == "ACTIVE" and not addon.get("health", {}).get("issues"),
        "single_nat_available": len(nat) == 1 and nat[0]["State"] == "available",
        "rds_available_private_encrypted": database["DBInstanceStatus"] == "available" and not database["PubliclyAccessible"] and database["StorageEncrypted"],
        "rds_small_postgres16_with_protection": database["DBInstanceClass"] == "db.t4g.small" and database["Engine"] == "postgres" and database["EngineVersion"].startswith("16.") and database["DeletionProtection"],
        "rds_seven_day_backups_and_managed_secret": database["BackupRetentionPeriod"] == 7 and database.get("MasterUserSecret", {}).get("SecretStatus") == "active",
        "rds_storage_and_support_limits": database["AllocatedStorage"] == 20 and database["MaxAllocatedStorage"] == 40 and database["EngineLifecycleSupport"] == "open-source-rds-extended-support-disabled",
        "rds_force_ssl_enabled": any(p["ParameterName"] == "rds.force_ssl" and p["ParameterValue"] == "1" for p in parameters),
        "five_immutable_scanned_repositories": len(repositories) == 5 and all(r["imageTagMutability"] == "IMMUTABLE" and r["imageScanningConfiguration"]["scanOnPush"] for r in repositories),
        "five_empty_service_secret_containers": len(secrets) == 5 and all(not s.get("VersionIdsToStages") for s in secrets),
        "existing_cognito_preserved": outputs["cognito"]["userPoolId"] == "ap-south-1_aBuDlZ9RC" and outputs["cognito"]["userPoolClientId"] == "202ssal4mlube43ttm0j5m3k4i",
        "cluster_logs_seven_day_retention": any(g["logGroupName"] == "/aws/eks/wonderland-demo/cluster" and g.get("retentionInDays") == 7 for g in log_groups),
        "mock_checkout_configuration": 'MOCK_PAYMENTS_ENABLED: "true"' in (ROOT / "deploy/helm/wonderland/templates/config.yaml").read_text(),
    }
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "account": identity["Account"], "region": "ap-south-1", "status": "VERIFIED" if all(checks.values()) else "REVIEW_REQUIRED", "checks": checks,
              "cluster": "wonderland-demo", "nodegroup": "application", "node_count": len(node_data), "system_pod_count": len(pod_data), "database_engine_version": database["EngineVersion"], "pod_identity_agent_version": addon["addonVersion"],
              "checkout": "mock", "application_deployed": False, "database_password_read": False,
              "limitations": ["Foundation only; DB bootstrap, images, application workers, routing/frontend and hosted analytics remain", "Database metadata/TLS-required parameter verified; a live application TLS DB connection awaits the private bootstrap stage", "Final snapshot/recovery behavior is configured, not restore-tested", "AWS billing is delayed; no spending cap or automatic cleanup was created"]}
    (ROOT / "docs/evidence/step10-foundation-live-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not all(checks.values()):
        raise SystemExit("Foundation verification needs attention; inspect failed checks")


if __name__ == "__main__":
    main()
