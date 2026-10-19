"""Generate the bounded Step 09 CloudFormation experiment, not the full platform."""

import json
from pathlib import Path


def build_template():
    resources = {}

    def ref(name):
        return {"Ref": name}

    def attr(name, key):
        return {"Fn::GetAtt": [name, key]}

    def add(name, kind, **properties):
        resources[name] = {"Type": f"AWS::{kind}", "Properties": properties}

    def ingress(name, group, source, start, end=None, protocol="tcp"):
        add(
            name,
            "EC2::SecurityGroupIngress",
            GroupId=ref(group),
            SourceSecurityGroupId=ref(source),
            IpProtocol=protocol,
            **({"FromPort": start, "ToPort": end or start} if protocol != "-1" else {}),
        )

    add("Vpc", "EC2::VPC", CidrBlock="10.89.0.0/16", EnableDnsSupport=True, EnableDnsHostnames=True)
    add("InternetGateway", "EC2::InternetGateway")
    add(
        "GatewayAttachment",
        "EC2::VPCGatewayAttachment",
        VpcId=ref("Vpc"),
        InternetGatewayId=ref("InternetGateway"),
    )
    add("RouteTable", "EC2::RouteTable", VpcId=ref("Vpc"))
    add(
        "InternetRoute",
        "EC2::Route",
        RouteTableId=ref("RouteTable"),
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=ref("InternetGateway"),
    )
    resources["InternetRoute"]["DependsOn"] = "GatewayAttachment"
    for i in range(2):
        subnet = f"Subnet{i + 1}"
        add(
            subnet,
            "EC2::Subnet",
            VpcId=ref("Vpc"),
            CidrBlock=f"10.89.{i}.0/24",
            AvailabilityZone={"Fn::Select": [i, {"Fn::GetAZs": ""}]},
            MapPublicIpOnLaunch=True,
        )
        add(
            f"RouteAssociation{i + 1}",
            "EC2::SubnetRouteTableAssociation",
            RouteTableId=ref("RouteTable"),
            SubnetId=ref(subnet),
        )
    subnets = [ref("Subnet1"), ref("Subnet2")]
    for name in ["ControlPlaneSg", "NodeSg", "AlbSg", "LinkSg"]:
        add(name, "EC2::SecurityGroup", GroupDescription=f"Step09 {name}", VpcId=ref("Vpc"))
    ingress("NodeToControlPlane", "ControlPlaneSg", "NodeSg", 443)
    ingress("ControlPlaneToKubelet", "NodeSg", "ControlPlaneSg", 10250)
    ingress("ControlPlaneToWebhooks", "NodeSg", "ControlPlaneSg", 443)
    ingress("ControlPlaneToDnsTcp", "NodeSg", "ControlPlaneSg", 53)
    ingress("ControlPlaneToDnsUdp", "NodeSg", "ControlPlaneSg", 53, protocol="udp")
    ingress("NodeToNode", "NodeSg", "NodeSg", 0, protocol="-1")
    ingress("LinkToAlb", "AlbSg", "LinkSg", 80)
    ingress("AlbToNodePort", "NodeSg", "AlbSg", 30080)
    for name, service, policies in [
        ("ClusterRole", "eks.amazonaws.com", ["AmazonEKSClusterPolicy"]),
        (
            "NodeRole",
            "ec2.amazonaws.com",
            [
                "AmazonEKSWorkerNodePolicy",
                "AmazonEC2ContainerRegistryPullOnly",
                "AmazonEKS_CNI_Policy",
            ],
        ),
    ]:
        add(
            name,
            "IAM::Role",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": service},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            ManagedPolicyArns=[
                {"Fn::Sub": f"arn:${{AWS::Partition}}:iam::aws:policy/{p}"} for p in policies
            ],
        )
    add(
        "Cluster",
        "EKS::Cluster",
        Name={"Fn::Sub": "${AWS::StackName}"},
        Version=ref("KubernetesVersion"),
        RoleArn=attr("ClusterRole", "Arn"),
        UpgradePolicy={"SupportType": "STANDARD"},
        AccessConfig={
            "AuthenticationMode": "API",
            "BootstrapClusterCreatorAdminPermissions": False,
        },
        ResourcesVpcConfig={
            "SubnetIds": subnets,
            "SecurityGroupIds": [ref("ControlPlaneSg")],
            "EndpointPrivateAccess": True,
            "EndpointPublicAccess": True,
            "PublicAccessCidrs": [ref("OperatorCidr")],
        },
    )
    add(
        "OperatorAccess",
        "EKS::AccessEntry",
        ClusterName=ref("Cluster"),
        PrincipalArn=ref("OperatorArn"),
        Type="STANDARD",
        AccessPolicies=[
            {
                "PolicyArn": {
                    "Fn::Sub": (
                        "arn:${AWS::Partition}:eks::aws:cluster-access-policy/"
                        "AmazonEKSClusterAdminPolicy"
                    )
                },
                "AccessScope": {"Type": "cluster"},
            }
        ],
    )
    add(
        "LaunchTemplate",
        "EC2::LaunchTemplate",
        LaunchTemplateData={
            "SecurityGroupIds": [ref("NodeSg")],
            "InstanceType": "t3.medium",
            "MetadataOptions": {"HttpTokens": "required", "HttpPutResponseHopLimit": 1},
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "VolumeSize": 20,
                        "VolumeType": "gp3",
                        "Encrypted": True,
                        "DeleteOnTermination": True,
                    },
                }
            ],
        },
    )
    add(
        "Nodes",
        "EKS::Nodegroup",
        ClusterName=ref("Cluster"),
        NodeRole=attr("NodeRole", "Arn"),
        Subnets=subnets,
        AmiType="AL2023_x86_64_STANDARD",
        CapacityType="ON_DEMAND",
        ScalingConfig={"MinSize": 1, "MaxSize": 1, "DesiredSize": 1},
        LaunchTemplate={
            "Id": ref("LaunchTemplate"),
            "Version": attr("LaunchTemplate", "LatestVersionNumber"),
        },
    )
    resources["Nodes"]["DependsOn"] = [
        "InternetRoute",
        "RouteAssociation1",
        "RouteAssociation2",
        "NodeToControlPlane",
        "ControlPlaneToKubelet",
        "NodeToNode",
    ]
    add(
        "Repository",
        "ECR::Repository",
        EmptyOnDelete=True,
        ImageTagMutability="IMMUTABLE",
        ImageScanningConfiguration={"ScanOnPush": True},
    )
    add(
        "TargetGroup",
        "ElasticLoadBalancingV2::TargetGroup",
        VpcId=ref("Vpc"),
        Protocol="HTTP",
        Port=30080,
        TargetType="instance",
        HealthCheckPath="/smoke/health",
        TargetGroupAttributes=[{"Key": "deregistration_delay.timeout_seconds", "Value": "10"}],
    )
    add(
        "LoadBalancer",
        "ElasticLoadBalancingV2::LoadBalancer",
        Scheme="internal",
        Type="application",
        Subnets=subnets,
        SecurityGroups=[ref("AlbSg")],
    )
    add(
        "Listener",
        "ElasticLoadBalancingV2::Listener",
        LoadBalancerArn=ref("LoadBalancer"),
        Port=80,
        Protocol="HTTP",
        DefaultActions=[{"Type": "forward", "TargetGroupArn": ref("TargetGroup")}],
    )
    add(
        "VpcLink",
        "ApiGatewayV2::VpcLink",
        Name={"Fn::Sub": "${AWS::StackName}"},
        SubnetIds=subnets,
        SecurityGroupIds=[ref("LinkSg")],
    )
    add("Api", "ApiGatewayV2::Api", Name={"Fn::Sub": "${AWS::StackName}"}, ProtocolType="HTTP")
    add(
        "Integration",
        "ApiGatewayV2::Integration",
        ApiId=ref("Api"),
        IntegrationType="HTTP_PROXY",
        IntegrationMethod="ANY",
        IntegrationUri=ref("Listener"),
        ConnectionType="VPC_LINK",
        ConnectionId=ref("VpcLink"),
        PayloadFormatVersion="1.0",
        TimeoutInMillis=10000,
        RequestParameters={"overwrite:path": "$request.path"},
    )
    add(
        "Route",
        "ApiGatewayV2::Route",
        ApiId=ref("Api"),
        RouteKey="GET /smoke/health",
        AuthorizationType="NONE",
        Target={"Fn::Join": ["/", ["integrations", ref("Integration")]]},
    )
    add(
        "Stage",
        "ApiGatewayV2::Stage",
        ApiId=ref("Api"),
        StageName="$default",
        AutoDeploy=True,
        DefaultRouteSettings={"ThrottlingBurstLimit": 5, "ThrottlingRateLimit": 2},
    )
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Wonderland Step09 isolated MOCK EKS / HTTP API feasibility experiment",
        "Parameters": {
            "OperatorArn": {
                "Type": "String",
                "AllowedPattern": "arn:aws:iam::708919751353:(role|user)/.+",
            },
            "OperatorCidr": {"Type": "String", "AllowedPattern": r"\d{1,3}(\.\d{1,3}){3}/32"},
            "KubernetesVersion": {
                "Type": "String",
                "Default": "1.35",
                "AllowedPattern": r"1\.\d{2}",
            },
        },
        "Resources": resources,
        "Outputs": {
            k: {"Value": v}
            for k, v in {
                "ClusterName": ref("Cluster"),
                "RepositoryUri": attr("Repository", "RepositoryUri"),
                "TargetGroupArn": ref("TargetGroup"),
                "VpcId": ref("Vpc"),
                "NodeGroupName": attr("Nodes", "NodegroupName"),
                "ApiEndpoint": attr("Api", "ApiEndpoint"),
                "ApiId": ref("Api"),
                "VpcLinkId": ref("VpcLink"),
            }.items()
        },
    }


if __name__ == "__main__":
    Path(__file__).with_name("cloudformation.json").write_text(
        json.dumps(build_template(), indent=2) + "\n", encoding="utf-8"
    )
