output "topics" { value = { for k, t in aws_sns_topic.events : k => t.arn } }
output "queues" { value = { for k, q in aws_sqs_queue.events : k => q.url } }
output "processing_dlqs" { value = { for k, q in aws_sqs_queue.processing_dlq : k => q.url } }
output "delivery_dlqs" { value = { for k, q in aws_sqs_queue.delivery_dlq : k => q.url } }
output "worker_roles" { value = { for k, r in aws_iam_role.worker : k => r.arn } }
