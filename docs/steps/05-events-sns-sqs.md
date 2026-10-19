# Step 05 — Transactional outbox and AWS SNS/SQS

The event code and AWS messaging stack are implemented. The bounded real-AWS delivery and dead-letter checks passed. **Continuous worker startup still requires your non-root IAM Identity Center login.** The two browser logins attempted so far selected root. Root cannot assume the scoped worker roles; do not replace the worker profiles with root as a workaround.

## 1. Understand what this step adds

Previously, Booking stored lifecycle events but did not deliver them. Catalog price changes were synchronous HTTP dependencies for new reservations. This lesson adds durable publishers, SNS fanout, separate SQS queues, retry/dead-letter handling, consumer inboxes and versioned projections.

```mermaid
flowchart LR
  Admin[Angular administrator publishes price] --> Catalog[Catalog transaction]
  Catalog --> CO[(Catalog price + audit + outbox)]
  CO --> CP[Catalog publisher]
  CP --> CT[SNS Catalog topic]
  CT --> PQ[SQS Booking prices]
  PQ --> BC[Booking pricing consumer]
  BC --> BP[(Booking inbox + price projection)]
  UI[Angular reservation] --> Booking[Booking transaction]
  BP --> Booking
  Booking --> BO[(Booking + capacity + outbox)]
  BO --> BPub[Booking publisher]
  BPub --> BT[SNS Booking topic]
  BT --> AQ[SQS Analytics bookings]
  BT --> PayQ[SQS Payment bookings]
  AQ --> AC[Analytics consumer]
  AC --> AP[(Analytics inbox + booking projection)]
  PayQ --> Future[Payment consumer in Step 06]
```

SNS distributes copies to subscribers. Each consumer has its own SQS queue, so Analytics and Payment do not compete for the same message. SNS/SQS Standard delivery is at least once and may be out of order. The design handles this with stable event IDs and full snapshots carrying increasing aggregate versions. It does not claim exactly-once transport. [AWS standard queue behavior](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html)

## 2. What is already deployed in your account

Region: **Mumbai, ap-south-1**. Stack: **wonderland-events-dev**, account ending **1353**, status verified `CREATE_COMPLETE`.

The reproducible template is `infra/events/sns-sqs.json`:

| Resource | Purpose |
|---|---|
| SNS `wonderland-events-dev-catalog` | Versioned package price snapshots |
| SNS `wonderland-events-dev-booking` | Pending/cancelled/expired booking lifecycle snapshots |
| SQS `wonderland-events-dev-booking-prices` | Booking's pricing consumer |
| SQS `wonderland-events-dev-analytics-bookings` | Analytics lifecycle consumer |
| SQS `wonderland-events-dev-payment-bookings` | Durable queue reserved for Step 06 |
| A `-dlq` queue for each consumer | Messages that repeatedly fail application processing |
| SQS `wonderland-events-dev-delivery-dlq` | SNS subscription delivery failures |
| Four scoped IAM roles | Two publishers and two consumers |

The topics use the AWS managed SNS KMS key. Queues use SQS managed server-side encryption. Queue resource policies permit SNS `SendMessage` only from the expected topic and account; they do not allow anonymous access. Subscriptions use **raw message delivery**, so consumers receive the application JSON envelope directly. [AWS raw delivery documentation](https://docs.aws.amazon.com/sns/latest/dg/sns-large-payload-raw-message-delivery.html)

Consumer queues use 20-second long polling, a 60-second visibility timeout, 14-day retention and a processing DLQ after `maxReceiveCount=5`. Delivery DLQs also retain for 14 days. The application processes one message at a time, keeping database operations short. Future work that can exceed 60 seconds must extend visibility while processing.

SNS delivery failure and application processing failure are different. The SNS subscription's redrive policy catches delivery to SQS that SNS cannot complete. The source queue's redrive policy catches messages a consumer receives repeatedly without acknowledging. [AWS SNS DLQ documentation](https://docs.aws.amazon.com/sns/latest/dg/sns-dead-letter-queues.html)

The Payment queue has no consumer yet. Its messages are retained for at most 14 days; it is not permanent storage. Preserve/replay events deliberately when developing Step 06, and do not interpret an old pending-payment event as proof that a hold is still valid.

AWS usage is billable. No compute instances, RDS cluster, notification emails or paid dashboard service were created in this step. Check your Billing console and the current [SNS pricing](https://aws.amazon.com/sns/pricing/) and [SQS pricing](https://aws.amazon.com/sqs/pricing/) for your account's allowances. Empty long polls also make requests; stop local workers when you finish practicing.

## 3. Finish the non-root temporary login

The signed AWS CLI is available locally at `.local/tools/aws-cli/Amazon/AWSCLIV2/aws.exe`. System-wide installation failed, so the signed installer was extracted inside the ignored project folder. Nothing changed your global PATH.

Two separate profiles are intentional:

- `wonderland-dev`: temporary deployment session; currently root, used for provisioning and explicitly bounded diagnostics only.
- `wonderland-worker-source`: your non-root SSO session, which the four runtime profiles will use as their source.

For **IAM Identity Center**, first obtain your access portal URL (usually `https://...awsapps.com/start`) and the region where Identity Center was configured. Its region can differ from Mumbai, where this project's queues live. Do not use a Cognito visitor login here: Cognito authenticates application users and does not grant AWS administration permissions.

Run in an interactive PowerShell terminal from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\aws-sso-setup.ps1
```

AWS prompts for an SSO session name, portal URL, Identity Center region and registration scopes. Use the portal's actual region and the usual `sso:account:access` scope. Complete password/MFA/authorization directly in AWS. Select account **708919751353** and your authorized permission set. Set the client default region to **ap-south-1** and output to JSON. Never send passwords, MFA codes or tokens in chat.

To verify and later refresh the SSO session in PowerShell:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-worker-source --region ap-south-1
& $LocalAws sso login --profile wonderland-worker-source
```

The identity should be a non-root principal for this account, normally an assumed SSO role. `arn:aws:iam::708919751353:root` is the wrong identity for the runtime source profile.

`AWS_CONFIG_FILE` and the AWS-login cache live under ignored `.local/aws`. AWS CLI's Identity Center SSO cache uses its normal per-user location. Keep both caches private. Root credentials or access keys must not be copied into service `.env` files or container images. The SDK supports temporary profiles, and the installed CRT dependency supports the newer browser-login credential mechanism. [AWS temporary browser login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html), [Boto3 credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

For an IAM user/federated console login instead of Identity Center, `scripts/aws-login.ps1 -Profile wonderland-worker-source` uses `aws login`. That is a different flow from `aws configure sso`; choose the method matching your real identity provider.

## 4. Configure and verify scoped runtime roles

After SSO login:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-events.ps1
```

The script reads CloudFormation outputs into ignored `.local/events.json` and configures these profiles:

| Profile | Allowed runtime operations |
|---|---|
| `wonderland-catalog-publisher` | Publish only to Catalog topic; SNS KMS usage via SNS in this account |
| `wonderland-booking-publisher` | Publish only to Booking topic; SNS KMS usage via SNS in this account |
| `wonderland-booking-consumer` | Receive/delete/change visibility/read attributes on Booking prices queue |
| `wonderland-analytics-consumer` | Receive/delete/change visibility/read attributes on Analytics bookings queue |

Their `source_profile` is `wonderland-worker-source`. No access keys are created. Role sessions last up to one hour and can refresh while the source login is valid.

Verify each profile, for example:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-catalog-publisher --region ap-south-1
```

If `AssumeRole` is denied for a non-root identity, its permission set needs `sts:AssumeRole` on the four role ARNs in `.local/events.json`. Ask the administrator who manages that permission set to add only those resources. The stack's current trust delegates to this AWS account; identity permissions must still allow role assumption. If your SSO identity belongs to another account, do not widen trust casually: use the intended project account or explicitly review a trust change.

If you deploy this stack elsewhere, validate the template and create a CloudFormation change set using `CAPABILITY_IAM` and the intended development principal/account trust. Existing-account commands and parameter values are recorded in this lesson; do not blindly deploy a duplicate stack. No EKS workload role bindings are implemented yet.

## 5. Prepare the local databases and APIs

From `D:\Courses\Microservices`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
docker compose up -d --build catalog booking booking-maintenance analytics-migrate
```

Setup installs the SDK, applies Catalog/Booking migrations, bootstraps separate Analytics roles/schema and applies its initial inbox/projection migration. Compose's bootstrap jobs are serialized because concurrent database permission grants can conflict. Existing data and Step 04 booking history are preserved.

The service Docker build context is now the repository root so each image can copy `packages/common/wonderland_events`. The root `.dockerignore` excludes credentials, caches, virtual environments and frontend artifacts.

The APIs still do not need AWS credentials. Local event workers run on the host, where the temporary SSO profile is available. Cloud deployment will use workload IAM roles instead. Do not mount your entire AWS credential directory into every application container.

Analytics `.env` contains its own local role:

```dotenv
DATABASE_URL=postgresql+psycopg://analytics_dev:analytics_dev_only@127.0.0.1:55432/wonderland
AWS_REGION=ap-south-1
BOOKING_QUEUE_URL=
```

The startup script supplies the queue URL from stack outputs. This early Analytics worker stores booking lifecycle snapshots only; revenue, attraction usage and BI dashboards arrive in Step 08.

## 6. Bootstrap prices and run the four workers

First enqueue the current four prices so Booking can initialize an empty projection:

```powershell
. .\scripts\aws-common.ps1
Push-Location services/catalog
& $ProjectPython -m app.event_worker snapshot
Pop-Location
```

This writes full price snapshots through Catalog's outbox; it does not let Booking read Catalog's database. Existing prices are preserved. Repeating the command emits new IDs with the same aggregate version, which the projection safely ignores when it already has that version.

Run each worker in its own PowerShell terminal from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-events.ps1 -Worker catalog-publish
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-events.ps1 -Worker booking-prices
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-events.ps1 -Worker booking-publish
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-events.ps1 -Worker analytics
```

The scripts choose the corresponding scoped AWS profile. `-Once` performs one publish or one receive call for troubleshooting. It does not drain an entire queue. Continuous workers are intentionally not started under root. A worker process exits on an unhandled connection/credential failure; inspect the error and restart after fixing it. Automatic production supervision is future deployment work.

Read local outbox/inbox counts and approximate AWS queue depths:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\event-status.ps1
```

The status script uses the deployment profile for queue inspection; runtime consumer roles intentionally lack access to other consumers' queues or DLQs. Watch failed outbox counts, DLQ depth, source-queue oldest message age and SNS delivery failures. No CloudWatch alarms or notification destinations were created in this step; configure those with the later cloud monitoring milestone.

## 7. Enable Booking's event-driven pricing after synchronization

Verify the four current package versions have arrived using the bounded check:

```powershell
.\.venv\Scripts\python.exe scripts/verify-event-delivery.py
```

The default uses the four scoped roles, enqueues current price snapshots, drains bounded work, checks both projections and redelivers one exact price event. It publishes real retained local application events to your AWS account, so use it in this development environment.

Once this passes and the pricing worker remains running, set the following in `services/booking/.env`:

```dotenv
PRICING_MODE=projection
```

Then recreate Booking so it reads the new setting:

```powershell
docker compose up -d --force-recreate booking
```

For a host reload server, restart `scripts/start-booking.ps1` instead. Angular endpoints remain the same. In projection mode, Python uses Booking's own `ticket_price_projection` inside the booking transaction and makes no Catalog HTTP quote call. There is no automatic fallback. An unsynchronized package returns 503, and a price-version mismatch returns 409.

Until continuous SSO workers are verified, the current development `.env` remains in HTTP mode to preserve the working Step 04 application. Projection mode exists and is tested; the switch is an explicit rollout step.

Event pricing is eventually consistent. An older reviewed price can be accepted while its matching projection version is still current locally, before a newer Catalog event arrives. A form showing a newer version than the projection is rejected until synchronization. This design does not claim instantaneous global price publication. Existing bookings retain their original price snapshots after future updates.

## 8. Follow the implementation file by file

| File | Responsibility |
|---|---|
| `infra/events/sns-sqs.json` | Topics, queues, redrive/resource policies, encryption and worker roles |
| `packages/common/wonderland_events/transport.py` | Event envelope, publisher, retry policy, inbox processing and acknowledgement |
| `services/catalog/app/events.py` | Full price snapshots written in the domain transaction; bootstrap snapshots |
| `services/catalog/app/api/admin.py` | Price + audit + outbox commit atomically |
| `services/catalog/app/event_worker.py` | Publisher/status/snapshot/requeue commands |
| `services/catalog/alembic/versions/0003_event_outbox.py` | Catalog delivery storage and pending index |
| `services/booking/alembic/versions/0002_event_delivery.py` | Delivery metadata, existing-event backfill, inbox and pricing projection |
| `services/booking/booking_app/main.py` | Increasing booking event version; optional projection quote lookup |
| `services/booking/booking_app/pricing_projection.py` | Validated versioned snapshot upserts |
| `services/booking/booking_app/event_worker.py` | Booking publisher and pricing consumer |
| `services/analytics/analytics_app/worker.py` | Durable receipt + latest booking lifecycle snapshot |
| `services/analytics/alembic/versions/0001_inbox.py` | Independent Analytics tables/migration version |
| `scripts/start-events.ps1` | Scoped local worker startup |
| `scripts/verify-event-delivery.py` | Bounded real-AWS delivery/projection/duplicate check |
| `scripts/verify-sqs-redrive.py` | Isolated disposable-queue dead-letter check |

### Publisher safety

A database transaction writes the domain change and outbox event together. The publisher selects one due row with `FOR UPDATE SKIP LOCKED`, calls SNS, and stores the SNS message ID and publication timestamp. Different publisher replicas skip locked rows. Network calls have bounded SDK timeouts/retries; the row lock is held during that short send.

If SNS accepts a message but the response or database commit is lost, the row can be published again. Its event ID remains the same. Do not generate a fresh ID when retrying a persisted row.

Failed sends record only an error code/type, increment attempts and schedule exponential delays capped at 300 seconds. After ten failed attempts, `failed_at` retains the row for investigation. This local failed-outbox state is separate from AWS DLQs. No event is deleted automatically.

After fixing the cause, requeue one failed row using its real event UUID:

```powershell
# Run from services/catalog with shared PYTHONPATH set by aws-common.ps1:
& $ProjectPython -m app.event_worker requeue --event-id <event-uuid>
# Booking equivalent, from services/booking:
& $ProjectPython -m booking_app.event_worker requeue --event-id <event-uuid>
```

Replace the placeholder; PowerShell angle brackets are explanatory. A published event is not reset by this command. Replay of already published events requires a deliberate replay procedure, not setting every outbox row back to pending.

### Consumer safety

The consumer validates the envelope/type/source/version and inserts `(consumer, event_id, payload_hash)` in its own inbox. It updates the projection in the same transaction. Only after commit does it call SQS DeleteMessage. A failure before commit leaves no receipt or projection change and no acknowledgement.

A crash or delete failure after commit causes another delivery. The inbox recognizes the same event ID and acknowledges without applying it again. Reusing the same ID with a different canonical payload is rejected. Full snapshots update a projection only when their aggregate version is greater, so an older event cannot undo a newer cancellation or price.

Envelope fields are `event_id`, `schema_version=1`, `event_type`, `source`, `aggregate_id`, `aggregate_version`, `occurred_at` and `data`. Booking aggregate versions increase under the existing slot lock. Price aggregate versions match Catalog price versions. Consumers do not assume SQS arrival order.

## 9. Practice the complete flow

1. Finish non-root SSO, configure roles and start all four workers.
2. Run the bounded delivery check and enable projection mode as described above.
3. In Angular `/admin`, publish a changed package price. Verify Catalog's outbox is published and Booking receives the matching version.
4. In `/book`, reload prices, review a reservation and submit. Check its immutable price/version.
5. Open `/bookings`, cancel the unpaid hold and verify Analytics eventually shows the newer cancelled snapshot.
6. Stop only the Catalog publisher. Publish another price and observe the durable pending outbox row. Restart the publisher and confirm catch-up without redoing the administrator change.
7. Stop only the pricing consumer. Observe queued messages. Restart it and confirm it processes them.
8. Stop only Analytics. Booking remains available while its queue buffers events.
9. Read all DLQ depths. A nonzero value needs investigation; do not purge messages to make the numbers look healthy.

For failures, inspect local publisher error codes and logs, AWS topic subscription confirmation/queue policies, KMS permissions, profile expiry, queue region and `ApproximateReceiveCount`. AWS queues are not a permanent event archive: retention is bounded, and local outboxes/inboxes need a future audited retention/replay policy.

## 10. Verification and current boundaries

Run all local checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

The local Python suite includes real PostgreSQL transactions and mocked AWS boundaries; the smoke scripts separately test real AWS. The deployment-session smoke is explicitly available as `verify-event-delivery.py --deployment-smoke` for a bounded provisioning diagnostic. It must not be used as a continuous root worker launcher.

The isolated redrive check creates two uniquely named `wonderland-step05-test-*` queues, sends a constant test message, deliberately leaves it unacknowledged, observes movement after two receives, and removes only those temporary queues. It never receives or purges application queues. This verifies SQS redrive; it does not simulate an SNS subscription outage.

See `docs/evidence/step05-validation.md` for exact observed results and remaining SSO work. Payment processing, paid confirmations, ticket issuance, admissions and BI are still future milestones. Before Step 06, redesign unpaid hold expiry/cancellation around provider reconciliation and late callbacks; this event transport alone does not solve payment races.

## 11. Stop, costs and teardown

Stop host workers using Ctrl+C in their four terminals. `scripts/stop-local.ps1` stops Docker services but does not stop independent host workers or delete AWS resources. Empty queues/topics remain in AWS. Temporary logins expire; refresh SSO when needed.

For intentional teardown, first stop workers, inspect all pending outboxes and queues, and preserve any demonstration evidence. Deleting the CloudFormation stack deletes the queues and their retained messages and the scoped IAM roles. Do not delete Cognito or the local database volume as part of event-stack teardown. Use the AWS console to review and delete only `wonderland-events-dev` when you deliberately finish the experiment.
