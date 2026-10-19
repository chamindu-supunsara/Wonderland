resource "aws_iam_role" "controller" {
  name = "wonderland-demo-target-controller"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Principal = { Service = "pods.eks.amazonaws.com" }, Action = ["sts:AssumeRole", "sts:TagSession"],
    Condition = { StringEquals = { "aws:RequestTag/kubernetes-namespace" = "kube-system", "aws:RequestTag/kubernetes-service-account" = "aws-load-balancer-controller", "aws:RequestTag/eks-cluster-arn" = "arn:aws:eks:ap-south-1:708919751353:cluster/wonderland-demo" } }
  }] })
}
resource "aws_iam_role_policy" "controller" {
  name = "OnlyExistingTargetRegistration"
  role = aws_iam_role.controller.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ec2:DescribeAvailabilityZones", "ec2:DescribeInstances", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSecurityGroups", "ec2:DescribeSubnets", "ec2:DescribeVpcs", "ec2:DescribeTags", "elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeLoadBalancerAttributes", "elasticloadbalancing:DescribeListeners", "elasticloadbalancing:DescribeListenerAttributes", "elasticloadbalancing:DescribeRules", "elasticloadbalancing:DescribeTargetGroups", "elasticloadbalancing:DescribeTargetGroupAttributes", "elasticloadbalancing:DescribeTargetHealth", "elasticloadbalancing:DescribeTags"], Resource = "*" },
    { Effect = "Allow", Action = ["elasticloadbalancing:RegisterTargets", "elasticloadbalancing:DeregisterTargets"], Resource = [for t in aws_lb_target_group.api : t.arn] }
  ] })
}
resource "aws_eks_pod_identity_association" "controller" {
  cluster_name    = "wonderland-demo"
  namespace       = "kube-system"
  service_account = "aws-load-balancer-controller"
  role_arn        = aws_iam_role.controller.arn
  depends_on      = [aws_iam_role_policy.controller]
}
