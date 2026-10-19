"""Read-only verification of the exact Step09 resources saved before cleanup."""

import argparse
import json
import os
from datetime import UTC, datetime

import cloud_feasibility as cloud


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="wonderland-feasibility")
    args = parser.parse_args()
    os.environ.update(
        AWS_CONFIG_FILE=str(cloud.ROOT / ".local/aws/config"),
        AWS_LOGIN_CACHE_DIRECTORY=str(cloud.ROOT / ".local/aws/login/cache"),
        AWS_EC2_METADATA_DISABLED="true",
    )
    cloud.identity(args.profile)
    saved = json.loads((cloud.STATE / "before-cleanup.json").read_text())
    tags = {tag["Key"]: tag["Value"] for tag in saved.get("Tags", [])}
    if (
        saved["StackName"] != cloud.STACK
        or tags.get("Purpose") != "Step09MOCK"
        or f":{cloud.ACCOUNT}:stack/{cloud.STACK}/" not in saved["StackId"]
    ):
        raise RuntimeError("Saved cleanup evidence does not match this account/experiment")
    resources = json.loads((cloud.STATE / "cleanup-resources.json").read_text())["StackResources"]
    if any(resource["StackId"] != saved["StackId"] for resource in resources):
        raise RuntimeError("Cleanup resource IDs belong to a different stack attempt")
    ids = {r["LogicalResourceId"]: r.get("PhysicalResourceId") for r in resources}
    inventory = json.loads((cloud.STATE / "live-node-inventory.json").read_text())
    instances = [i for r in inventory["instances"]["Reservations"] for i in r["Instances"]]
    if not instances or any(instance["VpcId"] != ids["Vpc"] for instance in instances):
        raise RuntimeError("Worker inventory belongs to a different experiment VPC")
    volume_ids = [v["VolumeId"] for v in inventory["volumes"].get("Volumes", [])]
    asg_names = [g["AutoScalingGroupName"] for g in inventory["auto_scaling"]["AutoScalingGroups"]]
    report = {"checked_at": datetime.now(UTC).isoformat(), "remaining": {}}

    def aws(*parts):
        return cloud.aws(args.profile, *parts)

    def absent(*parts, missing):
        try:
            return aws(*parts)
        except RuntimeError as error:
            if missing not in str(error):
                raise
            return None

    report["stack"] = absent(
        "cloudformation", "describe-stacks", "--stack-name", cloud.STACK, missing="does not exist"
    )
    remaining = report["remaining"]
    remaining["clusters"] = [n for n in aws("eks", "list-clusters")["clusters"] if n == cloud.STACK]
    for key, service, action, collection, field, expected in [
        ("apis", "apigatewayv2", "get-apis", "Items", "ApiId", ids["Api"]),
        ("vpc_links", "apigatewayv2", "get-vpc-links", "Items", "VpcLinkId", ids["VpcLink"]),
        (
            "load_balancers",
            "elbv2",
            "describe-load-balancers",
            "LoadBalancers",
            "LoadBalancerArn",
            ids["LoadBalancer"],
        ),
        (
            "target_groups",
            "elbv2",
            "describe-target-groups",
            "TargetGroups",
            "TargetGroupArn",
            ids["TargetGroup"],
        ),
        (
            "repositories",
            "ecr",
            "describe-repositories",
            "repositories",
            "repositoryName",
            ids["Repository"],
        ),
    ]:
        remaining[key] = [
            x for x in aws(service, action).get(collection, []) if x[field] == expected
        ]
    for key, action, collection in [
        ("vpcs", "describe-vpcs", "Vpcs"),
        ("network_interfaces", "describe-network-interfaces", "NetworkInterfaces"),
        ("subnets", "describe-subnets", "Subnets"),
        ("security_groups", "describe-security-groups", "SecurityGroups"),
    ]:
        remaining[key] = aws("ec2", action, "--filters", f"Name=vpc-id,Values={ids['Vpc']}")[
            collection
        ]
    current_instances = aws(
        "ec2", "describe-instances", "--filters", f"Name=vpc-id,Values={ids['Vpc']}"
    )["Reservations"]
    remaining["active_instances"] = [
        i
        for reservation in current_instances
        for i in reservation["Instances"]
        if i["State"]["Name"] != "terminated"
    ]
    remaining["volumes"] = (
        aws(
            "ec2", "describe-volumes", "--filters", "Name=volume-id,Values=" + ",".join(volume_ids)
        )["Volumes"]
        if volume_ids
        else []
    )
    remaining["auto_scaling_groups"] = aws(
        "autoscaling", "describe-auto-scaling-groups", "--auto-scaling-group-names", *asg_names
    )["AutoScalingGroups"]
    remaining["launch_templates"] = [
        template
        for template in aws("ec2", "describe-launch-templates")["LaunchTemplates"]
        if template["LaunchTemplateId"] == ids["LaunchTemplate"]
    ]
    for key, action, collection, field, expected in [
        (
            "internet_gateways",
            "describe-internet-gateways",
            "InternetGateways",
            "InternetGatewayId",
            ids["InternetGateway"],
        ),
        ("route_tables", "describe-route-tables", "RouteTables", "RouteTableId", ids["RouteTable"]),
    ]:
        remaining[key] = [
            item for item in aws("ec2", action)[collection] if item[field] == expected
        ]
    remaining["iam_roles"] = [
        role
        for name in [ids["ClusterRole"], ids["NodeRole"]]
        if (role := absent("iam", "get-role", "--role-name", name, missing="NoSuchEntity"))
    ]
    profiles = {
        i["IamInstanceProfile"]["Arn"].rsplit("/", 1)[1]
        for i in instances
        if "IamInstanceProfile" in i
    }
    remaining["instance_profiles"] = [
        item
        for name in profiles
        if (
            item := absent(
                "iam",
                "get-instance-profile",
                "--instance-profile-name",
                name,
                missing="NoSuchEntity",
            )
        )
    ]
    report["preserved"] = {
        "messaging_stack": aws(
            "cloudformation", "describe-stacks", "--stack-name", "wonderland-events-dev"
        )["Stacks"][0]["StackStatus"],
        "cognito_pool": aws(
            "cognito-idp", "describe-user-pool", "--user-pool-id", "ap-south-1_aBuDlZ9RC"
        )["UserPool"]["Id"],
    }
    report["verified"] = report["stack"] is None and not any(remaining.values())
    cloud.save("cleanup-verification.json", report)
    print(
        json.dumps(
            {
                "verified": report["verified"],
                "remaining_counts": {k: len(v) for k, v in remaining.items()},
                "preserved": report["preserved"],
            },
            indent=2,
        )
    )
    if not report["verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
