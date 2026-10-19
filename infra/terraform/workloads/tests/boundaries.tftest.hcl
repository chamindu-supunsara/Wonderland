mock_provider "aws" {
  mock_data "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:ap-south-1:708919751353:key/6b58a8d4-d66d-4ad1-a5ec-c498d4f35dec" }
  }
}
run "isolated_event_transport" {
  command = plan
  assert {
    condition     = length(aws_sns_topic.events) == 3 && length(aws_sqs_queue.events) == 3 && length(aws_sqs_queue.processing_dlq) == 3 && length(aws_sqs_queue.delivery_dlq) == 3
    error_message = "Use three isolated topics/routes with both processing and delivery DLQs."
  }
  assert {
    condition     = alltrue([for q in aws_sqs_queue.events : q.sqs_managed_sse_enabled && q.visibility_timeout_seconds == 60 && q.receive_wait_time_seconds == 20])
    error_message = "Queues must be encrypted and use bounded visibility with long polling."
  }
  assert {
    condition     = length(aws_iam_role.worker) == 6 && length(aws_eks_pod_identity_association.worker) == 6 && alltrue([for a in aws_eks_pod_identity_association.worker : a.namespace == "wonderland" && a.cluster_name == "wonderland-demo"])
    error_message = "Each AWS event worker needs its own identity in the existing cluster."
  }
}
