resource "aws_iam_role" "cluster" {
  name = "${local.name}-cluster"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${local.name}/cluster"
  retention_in_days = 7
}
resource "aws_eks_cluster" "main" {
  name                      = local.name
  role_arn                  = aws_iam_role.cluster.arn
  version                   = var.kubernetes_version
  enabled_cluster_log_types = ["api", "audit", "authenticator"]
  upgrade_policy { support_type = "STANDARD" }
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }
  vpc_config {
    subnet_ids              = aws_subnet.compute[*].id
    security_group_ids      = [aws_security_group.control.id]
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = [var.operator_cidr]
  }
  lifecycle {
    precondition {
      condition     = contains([for version in data.aws_eks_cluster_versions.standard.cluster_versions : version.cluster_version], var.kubernetes_version)
      error_message = "Requested EKS version is not in Mumbai standard support."
    }
  }
  depends_on = [aws_iam_role_policy_attachment.cluster, aws_cloudwatch_log_group.cluster]
}
resource "aws_eks_access_entry" "operator" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.operator_arn
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "operator" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_eks_access_entry.operator.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope { type = "cluster" }
}
resource "aws_iam_role" "nodes" {
  name = "${local.name}-nodes"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_iam_role_policy_attachment" "nodes" {
  for_each   = toset(["AmazonEKSWorkerNodePolicy", "AmazonEC2ContainerRegistryPullOnly", "AmazonEKS_CNI_Policy"])
  role       = aws_iam_role.nodes.name
  policy_arn = "arn:aws:iam::aws:policy/${each.key}"
}
resource "aws_launch_template" "nodes" {
  name_prefix            = "${local.name}-"
  instance_type          = "t3.medium"
  vpc_security_group_ids = [aws_security_group.nodes.id]
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }
}
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "application"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = aws_subnet.compute[*].id
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"
  scaling_config {
    desired_size = var.node_count
    min_size     = var.node_count
    max_size     = var.node_count
  }
  launch_template {
    id      = aws_launch_template.nodes.id
    version = aws_launch_template.nodes.latest_version
  }
  depends_on = [aws_iam_role_policy_attachment.nodes, aws_route.egress, aws_route_table_association.compute, aws_vpc_security_group_ingress_rule.node_to_control, aws_vpc_security_group_ingress_rule.control_to_node, aws_vpc_security_group_ingress_rule.nodes_internal]
}
data "aws_eks_addon_version" "pod_identity" {
  addon_name         = "eks-pod-identity-agent"
  kubernetes_version = var.kubernetes_version
  most_recent        = true
}
resource "aws_eks_addon" "pod_identity" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "eks-pod-identity-agent"
  addon_version = data.aws_eks_addon_version.pod_identity.version
  depends_on    = [aws_eks_node_group.main]
}
resource "aws_ecr_repository" "service" {
  for_each             = local.services
  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration { scan_on_push = true }
}
