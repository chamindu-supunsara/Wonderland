# Step 05 SNS/SQS infrastructure

`sns-sqs.json` is the deployed CloudFormation template for `wonderland-events-dev` in Mumbai. It creates two encrypted SNS topics, three consumer queues, three processing DLQs, an SNS delivery DLQ, restricted topic-to-queue policies, raw subscriptions and four scoped worker roles.

See [Step 05](../../docs/steps/05-events-sns-sqs.md) for deployment/authentication, startup, diagnostics, retention, cost and teardown instructions. No static access keys, public queue policy, external notification destination or EKS compute resource is included.
