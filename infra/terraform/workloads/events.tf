resource "aws_sns_topic" "events" {
  for_each          = toset(["catalog", "booking", "admission"])
  name              = "${local.prefix}-${each.key}"
  kms_master_key_id = "alias/aws/sns"
}
resource "aws_sns_topic_policy" "tls" {
  for_each = aws_sns_topic.events
  arn      = each.value.arn
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    # SNS resource policies reject service-wide wildcards that include non-topic actions.
    Sid = "RequireTLS", Effect = "Deny", Principal = "*",
    Action = ["sns:Publish", "sns:Subscribe", "sns:GetTopicAttributes", "sns:SetTopicAttributes",
    "sns:AddPermission", "sns:RemovePermission", "sns:DeleteTopic", "sns:ListSubscriptionsByTopic"], Resource = each.value.arn,
    Condition                                                                                                 = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_sqs_queue" "processing_dlq" {
  for_each                  = local.routes
  name                      = "${local.prefix}-${each.key}-dlq"
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600
  redrive_allow_policy = jsonencode({ redrivePermission = "byQueue",
  sourceQueueArns = ["arn:aws:sqs:${local.region}:${local.account}:${local.prefix}-${each.key}"] })
}
resource "aws_sqs_queue" "delivery_dlq" {
  for_each                  = local.routes
  name                      = "${local.prefix}-${each.key}-delivery-dlq"
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600
  redrive_allow_policy      = jsonencode({ redrivePermission = "denyAll" })
}
resource "aws_sqs_queue" "events" {
  for_each                   = local.routes
  name                       = "${local.prefix}-${each.key}"
  sqs_managed_sse_enabled    = true
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 60
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.processing_dlq[each.key].arn, maxReceiveCount = 5 })
}
locals {
  all_queues = merge(
    { for k, q in aws_sqs_queue.events : k => { url = q.url, arn = q.arn, topic = local.routes[k] } },
    { for k, q in aws_sqs_queue.delivery_dlq : "${k}-delivery" => { url = q.url, arn = q.arn, topic = local.routes[k] } },
    { for k, q in aws_sqs_queue.processing_dlq : "${k}-processing" => { url = q.url, arn = q.arn, topic = null } }
  )
}
resource "aws_sqs_queue_policy" "restricted" {
  for_each  = local.all_queues
  queue_url = each.value.url
  policy = jsonencode({ Version = "2012-10-17", Statement = concat([{
    Sid       = "RequireTLS", Effect = "Deny", Principal = "*", Action = "sqs:*", Resource = each.value.arn,
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }], each.value.topic == null ? [] : [{
    Sid    = "OnlyEnvironmentTopic", Effect = "Allow", Principal = { Service = "sns.amazonaws.com" },
    Action = "sqs:SendMessage", Resource = each.value.arn,
    Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.events[each.value.topic].arn },
    StringEquals = { "aws:SourceAccount" = local.account } }
  }]) })
}
resource "aws_sns_topic_subscription" "queue" {
  for_each             = local.routes
  topic_arn            = aws_sns_topic.events[each.value].arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.events[each.key].arn
  raw_message_delivery = true
  redrive_policy       = jsonencode({ deadLetterTargetArn = aws_sqs_queue.delivery_dlq[each.key].arn })
  depends_on           = [aws_sqs_queue_policy.restricted]
}
