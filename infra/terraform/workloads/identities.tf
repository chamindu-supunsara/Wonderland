resource "aws_iam_role" "worker" {
  for_each = local.identities
  name     = "${local.prefix}-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "pods.eks.amazonaws.com" }, Action = ["sts:AssumeRole", "sts:TagSession"],
    Condition = { StringEquals = {
      "aws:RequestTag/kubernetes-namespace"       = "wonderland"
      "aws:RequestTag/kubernetes-service-account" = "wonderland-${each.key}"
      "aws:RequestTag/eks-cluster-arn"            = "arn:aws:eks:${local.region}:${local.account}:cluster/wonderland-demo"
    } }
  }] })
}
resource "aws_iam_role_policy" "worker" {
  for_each = local.identities
  name     = "OnlyAssignedEventTransport"
  role     = aws_iam_role.worker[each.key].id
  policy = contains(keys(local.publishers), each.key) ? jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.events[each.value].arn] },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey*"], Resource = [data.aws_kms_key.sns.arn],
    Condition = { StringEquals = { "kms:ViaService" = "sns.ap-south-1.amazonaws.com" } } }
    ] }) : jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"], Resource = [aws_sqs_queue.events[each.key].arn] }
  ] })
}
resource "aws_eks_pod_identity_association" "worker" {
  for_each        = local.identities
  cluster_name    = "wonderland-demo"
  namespace       = "wonderland"
  service_account = "wonderland-${each.key}"
  role_arn        = aws_iam_role.worker[each.key].arn
  depends_on      = [aws_iam_role_policy.worker]
}
