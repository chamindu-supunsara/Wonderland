# Step 10E — private Metabase and the full mock guest analytics flow

Status: **complete for the approved mock scope**. Three private dashboards and eight saved questions survived Metabase Pod replacement. The hosted guest flow, aggregate reconciliation, TLS, private access and temporary-access removal passed. Checkout, Admission and Analytics remain explicitly mock. See [completion evidence](../evidence/step10e-completion.json).

## 1. What is being deployed

Metabase runs as one private Pod on the existing EKS nodes. Its application metadata uses the existing `wonderland_metabase` PostgreSQL database created in 10B. A separate read-only login can select nine aggregate reporting views in `wonderland`; it cannot read raw operational or guest identity tables or connect to the metadata database. Metadata and reporting database connections verify TLS with the RDS CA and hostname.

The official Metabase **v0.64.2.8** image is pinned by digest. PostgreSQL metadata, rather than an ephemeral H2 file, preserves users, settings, questions and dashboards across Pod replacement. Saved database connection credentials are encrypted with a generated `MB_ENCRYPTION_SECRET_KEY`; retain it with the metadata backup. See the [application database guide](https://www.metabase.com/docs/latest/installation-and-operation/configuring-application-database), [connection encryption](https://www.metabase.com/docs/latest/databases/encrypting-details-at-rest) and [official patch release](https://github.com/metabase/metabase/releases/tag/v0.64.2.8).

Metabase has a **ClusterIP Service only**. There is no public ingress, API Gateway route, Amplify rewrite or new load balancer for BI. Operators use authenticated EKS port-forwarding on `127.0.0.1:3001`, then a separate Metabase administrator login. This is a deliberate private demonstration workflow, not Cognito SSO or a dashboard visible to every visitor. Public sharing and embedding are disabled. Browser traffic uses loopback HTTP through the authenticated Kubernetes tunnel; the database uses verified TLS. This does not add end-to-end TLS to the application's existing private HTTP service hops.

## 2. Costs, capacity and retention

| Item | Planning amount |
|---|---:|
| Existing agreed foundation/workers/routing model | USD 62.41 |
| BI reserve: two Secrets Manager entries, image/storage/transfer and light usage | USD 2.00 |
| Combined model before exclusions | **USD 64.41** |
| Agreed allowance | **USD 75.00** |

No additional EC2, RDS, NAT or ALB is planned. Metabase requests 250 millicores and 1,536 MiB and is capped at one CPU and 2 GiB. The capacity check fails rather than adding a node automatically. The single BI replica can be unavailable during restart; it is not a high-availability design.

The fresh readiness snapshot in `docs/evidence/step10e-readiness.json` records available requested capacity and delayed Cost Explorer data. The reported USD 1.66 for 18 October is an estimated whole-account amount and omits later/unreported charges. It is not the final trial cost. Taxes, CPU credits, storage, transfer, retention and usage can vary; USD 75 is not an AWS-enforced cap.

Keep cleanup on **25 October 2026 at 6 PM Asia/Colombo**. Keep the two BI credentials and encryption key with the final database snapshot through the **8 November 2026 at 6 PM** recovery review. Only then review deletion with seven-day recovery. Terraform deliberately protects these credential containers from accidental destruction. Removing that protection or deleting retained material requires a deliberate review; no automatic deletion is configured.

## 3. Review and owner CloudShell preparation

Review these before applying:

- `docs/evidence/step10e-bi-plan.json`: exactly two new secret containers, no values in Terraform.
- `docs/evidence/step10e-access-review.json`: one temporary role and its EKS Pod Identity association.
- `docs/evidence/step10e-code-review.json`: tested source hashes and local image identities.
- `infra/bi/bootstrap-policy.json` and `bootstrap-access.json`: existing RDS master read, two named BI secrets read/write; no additional developer password-read grant.

The one-shot bootstrap must initialize database roles, migrate Analytics, grant aggregate views, generate credentials in Secrets Manager, and patch only the named Metabase runtime Secret in Kubernetes. Master credentials stay inside the temporary private Job. Analytics workers retain their own isolated database login. The bootstrap backfills only real persisted `MockBookingConfirmed` outbox events; it does not invent purchase facts.

After the exact temporary-access approval, upload `.local/deployment/step10e-bi-access.zip` in owner CloudShell. Compare its hash to the access review, extract it into a dedicated directory and run:

```bash
bash apply-access-cloudshell.sh --prepare
bash apply-access-cloudshell.sh --apply
```

The helper verifies the AWS account, immutable files, Access Analyzer findings and CloudFormation template. The owner setup session is required because chamindu's deployment role cannot grant itself access. Wait for `SUCCEEDED` before using the private Job.

## 4. Apply credentials and initialize the private database

In PowerShell from `D:\Courses\Microservices`:

```powershell
. ./scripts/aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
./scripts/deploy-cloud-bi.ps1 -ApplySecrets
./scripts/deploy-cloud-bi.ps1 -Bootstrap
```

The runner checks reviewed source/image hashes, uploads only the two reviewed immutable images to the existing analytics ECR repository, installs the public RDS CA and runs the bounded bootstrap Job. Its report must confirm the `analytics_0004` head, metadata/reporting TLS, restricted logins, read-only reporting and all named views. Logs contain sanitized outcomes, never passwords or raw SQL exception details.

Do not print Kubernetes Secret YAML, SecretString values or JDBC URIs in the terminal/chat. If a Job fails, inspect the sanitized report and repair the cause before a deliberate retry; do not remove completed/failed evidence blindly.

## 5. Roll out Analytics and Metabase

```powershell
./scripts/deploy-cloud-bi.ps1 -Deploy
./scripts/open-cloud-metabase.ps1
```

Only the two Analytics worker images change; Catalog, Booking, Payment, Admission, pricing projection, frontend origin and mock flags remain configured. Workers add successful-poll freshness and immutable simulated purchase facts. A heartbeat means polling is succeeding; it does not prove every message applied. Inspect inbox errors, queues and reporting reconciliation separately.

The initial Metabase startup exhausted its 256 MiB Java metaspace limit. The deployed chart removes that limit, caps the heap at 768 MiB and retains the existing 2 GiB container limit. Helm revision 2 is healthy on the original two nodes; no capacity was added. The initial and corrected source reviews are retained separately in evidence.

Keep the tunnel terminal open. Open **http://127.0.0.1:3001**. Closing the terminal disconnects private browser access; it does not stop cloud Metabase or its costs. Port 3000 remains the previous local Docker instance, so do not confuse its data with this cloud environment.

## 6. First Metabase administrator and reporting connection

Create the first Metabase administrator account and password directly in its setup page yourself. This is separate from Cognito. Keep the password in Metabase only; do not paste it into chat or scripts. Skip sample data and optional external telemetry.

Add a PostgreSQL connection named **Wonderland CLOUD MOCK Reporting**:

| Field | Value |
|---|---|
| Host | `wonderland-demo.cjqe46um8k52.ap-south-1.rds.amazonaws.com` |
| Port | `5432` |
| Database | `wonderland` |
| Username | `wl_metabase_reader` |
| Password | Generated reporting credential from `wonderland-demo/metabase-reporting`; enter it directly in Metabase |
| Schema scope | `reporting` only |
| SSL | Enabled, `verify-full`, with the RDS root CA certificate |

Retrieve only the reporting password through your authorized owner Secrets Manager session when needed and enter it in Metabase yourself. Do not use the master or metadata login for reporting. Do not share the password in chat. The password should be stored by Metabase only after its encrypted-connection setting is active. Follow the [PostgreSQL connection guide](https://www.metabase.com/docs/latest/databases/connections/postgresql).

Use read-only reporting; do not enable uploads, write actions, public sharing or embedding. Metabase's startup configuration-file provisioning is a paid Pro/Enterprise feature, so this open-source deployment uses normal setup and administration.

## 7. Build the cloud dashboards

Use the SQL files under `analytics/metabase/sql`. Create a dedicated **Wonderland CLOUD MOCK** collection and clearly distinguish cloud dashboards from the earlier local dashboards. Use query results, not static numbers or fabricated facts.

| Dashboard | Questions |
|---|---|
| CLOUD MOCK Operations | Daily arrivals, popular rides, peak/quiet hours, arrivals by tier |
| CLOUD MOCK Purchases | Purchases and simulated revenue by tier and confirmation date |
| CLOUD MOCK Pipeline Health | Totals/reconciliation, cloud successful-poll freshness |

Put hourly activity across the full dashboard width. Use Asia/Colombo. Purchase date is the confirmation date; visit date is simulated event time. Arrivals count guests checked in, not bookings or sold packages. Ride uses count individual rides; intentional repeat rides count, transport retries do not. Quiet hours are zero-filled across 24 hours for observed visit dates. Arrivals do not measure current occupancy because no checkout event exists. Simulated revenue is not real payment-provider revenue.

Saved cloud collection: **5**. Operations dashboard: **2**, questions **40–43**. Purchases dashboard: **3**, questions **44–45**. Pipeline Health dashboard: **4**, questions **46–47**. These IDs belong to the private cloud instance on port 3001, not the older local instance on port 3000. To reproduce a question manually: New → SQL query → Wonderland CLOUD MOCK Reporting → paste the matching SQL file → Get Answer → Visualization → Bar or Table → Save in Wonderland CLOUD MOCK. Create each dashboard with New → Dashboard, then Add questions and Save. The hourly card uses the full width.

The observed demonstration recorded one arrival at simulated 09:10 and Wonder Quest rides at 09:20 and 10:05 on 19 October. The duplicate check-in produced no extra arrival. The hourly grid shows arrival/ride counts 1/1 at 09:00, 0/1 at 10:00, and zero elsewhere. Two existing persisted mock purchases reconcile to two guest tickets and USD 80 simulated revenue. Three source outbox events match SNS publication IDs and committed Analytics inbox rows. The historical maximum observed delivery lag was 1.422082 seconds; this is a small demonstration, not a throughput guarantee.

## 8. Full hosted guest flow

1. Sign in to the hosted Wonderland app as a visitor. Select a future date/slot and package, reserve, choose **Simulate success**, then open the confirmed guest ticket. Each guest has its own `MOCK-...` reference.
2. Sign in as the application administrator. Open `/admin/admission`, paste that mock guest reference and choose **Look up ticket**.
3. Set a simulated Asia/Colombo time within the booked slot and select **Simulate guest check-in**. The slot end is excluded. Actual audit time is recorded separately from simulated visit time.
4. Select **Verify duplicate check-in**. Expect an explicit existing-entry response and no extra arrival fact.
5. Choose an active attraction and a time at or after check-in inside the slot. Select **Record mock ride usage**. Use a separate new submission only for another intentional ride.
6. Open the guest's visit history with the owning visitor account. Confirm the check-in and recorded rides. A different visitor must not see that guest's history.
7. Wait for Admission outbox → SNS → SQS → Analytics processing, then refresh the cloud dashboards. Record before/after totals: one new checked-in guest, the intended ride count, and no duplicate arrival. Confirm the corresponding simulated purchase uses the confirmation date/tier/amount.
8. Verify worker freshness, queue backlog/errors and unmatched ride reconciliation. A dashboard screenshot alone does not prove reliable event delivery; retain source/event/aggregate checks and transport metadata.

All records remain mock. No real money or physical admission is involved. Existing Step 10D mock ticket references can be reused for a check-in if their booking remains confirmed; choose simulated times within their recorded slots.

## 9. Persistence and temporary-access cleanup

Save dashboard/question identifiers and a sanitized evidence report. Restart only the Metabase Deployment and wait for readiness; reconnect the tunnel, sign in if needed, and verify saved dashboards and data remain. This demonstrates PostgreSQL metadata persistence, not a full disaster recovery exercise.

After database verification and configuration, remove the completed bootstrap release:

```powershell
./scripts/deploy-cloud-bi.ps1 -RemoveBootstrap
```

In the same reviewed owner bundle, run:

```bash
bash apply-access-cloudshell.sh --cleanup
```

Verify the temporary IAM role, Pod Identity association, Job, ServiceAccount and secret-writer Role/RoleBinding are absent. Runtime Metabase has no service-account token or AWS secret-read role. Keep its own named metadata runtime Secret and the two retained Secrets Manager entries; do not mistake them for temporary privileged access.

At trial teardown, export evidence, uninstall Metabase before RDS/EKS removal and follow the 10D → 10C → foundation dependency order. Retain the encryption key and metadata snapshot together through the agreed recovery review. Continue to Step 11 deployment automation and the remaining assignment feature/reliability/evidence milestones; this mock stage does not complete provider sandbox integration.

## 10. Completed verification and daily use

The stage passed 21 targeted tests, 10 database/TLS/privilege checks, 14 guest-flow checks, 5 outbox/SNS/inbox matching checks and 29 final live runtime/cleanup checks. Terraform's final plan has no changes. The three dashboards and eight questions remained available after the Metabase Deployment restarted; purchase and admission aggregates were unchanged. Queue and dead-letter backlogs were zero at the final observation. This verifies a bounded demonstration and Pod replacement, not load capacity, disaster recovery or final AWS charges.

To use the dashboards again:

```powershell
. ./scripts/aws-common.ps1
& $LocalAws sso login --profile wonderland-feasibility
./scripts/open-cloud-metabase.ps1
```

Keep the tunnel open, visit http://127.0.0.1:3001/collection/5-wonderland-cloud-mock and sign in using your separate Metabase administrator account. Open Operations, Purchases or Pipeline Health. Reload the dashboard for fresh query results. The tunnel was reconnected after the persistence test; closing it does not stop billable cloud resources.

Evidence: `step10e-database-verification.json`, `step10e-flow-verification.json`, `step10e-event-delivery.json`, `step10e-live-verification.json`, `step10e-dashboard-persistence.json`, and `step10e-completion.json` under `docs/evidence`. Screenshots include cloud Operations, Purchases, Pipeline Health, staff check-in, visitor ride history and temporary owner-access cleanup. The USD 64.41 model remains an estimate; review Billing as charges arrive and retain the 25 October cleanup deadline.
