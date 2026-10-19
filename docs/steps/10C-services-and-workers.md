# Step 10C — Python services and event workers on Helm

Status: **deployed and live verified**, completed **19 October 2026 at 12:00 AM Asia/Colombo**. Helm release `wonderland`, namespace `wonderland`, revision **2**, runs eight API replicas and seven independent workers on the original two nodes. All **34 final checks** passed, with zero application Pod restarts at verification. Pricing is in verified projection mode. See [deployment record](../evidence/step10c-deployment.json), [live checks](../evidence/step10c-live-verification.json), and [projection verification](../evidence/step10c-projection-smoke-verification.json).

The operator IP repair was approved and applied: EKS now allows `112.134.219.72/32` instead of the old `112.134.222.147/32`. No other foundation resource changed. Fresh node/Pod capacity checks passed before workload deployment, and a subsequent foundation plan reports no changes. See `docs/evidence/step10c-operator-ip-review.json`. If your public IP changes again, prepare another reviewed `/32` replacement; do not open access to `0.0.0.0/0`.

The commands below document the completed rollout and recovery procedure. Do not reapply the historical saved plan: its evidence is now marked applied, and the deployment runner rejects it. Future infrastructure changes require a fresh reviewed plan.

The existing two EKS workers and private RDS database are reused. Checkout, admission and analytics remain explicitly mock. This stage deploys private ClusterIP APIs; public routing, frontend hosting and authenticated browser walkthroughs belong to 10D/10E. Internal service HTTP is private; end-to-end service-hop TLS remains a 10D design/verification task. Database connections already require certificate-verified TLS.

## 1. Review the exact changes

The reviewed Terraform deployment created **45 resources**, with no replacements or deletions:

| Resources | Count | Purpose |
| --- | ---: | --- |
| SNS topics / topic TLS policies | 3 / 3 | Catalog, Booking and Admission, each encrypted with the existing AWS-managed SNS key |
| SQS queues / queue policies | 9 / 9 | Three consumers, each with a processing DLQ and an SNS delivery DLQ |
| SNS subscriptions | 3 | Raw envelope delivery, source-restricted queue policies |
| IAM roles / inline role policies / Pod Identity associations | 6 / 6 / 6 | Separate identity for each publisher or consumer |

The separate root is `infra/terraform/workloads`; encrypted/versioned S3 state uses `demo/workloads/terraform.tfstate`. It preserves the foundation state and older development messaging stack. APIs and booking maintenance receive no AWS workload role. None of these workload roles can read database passwords from Secrets Manager. Each Pod receives only its own precreated Kubernetes runtime Secret.

The first apply created 42 resources, then AWS rejected the topic policies' `sns:*` wildcard with `Policy statement action out of service scope`. We replaced it with explicit topic actions, reviewed a three-addition repair plan and applied only the missing policies. The resulting workload plan reports no changes. The original plan/source hashes and repair plan remain in evidence. State contains 45 managed resources plus one read-only KMS key data source.

Owner setup creates and attaches the customer-managed policy **WonderlandWorkloadsDeployment** to the existing WonderlandFeasibility permission set. The existing 10,102-byte inline policy stays unchanged. The new policy scopes ECR uploads to five exact repositories; SNS/SQS lifecycle to the listed new topics/queues; IAM lifecycle/inline policies/PassRole to six exact worker roles; and Pod Identity operations to the existing demo cluster. Review `operator-policy.json`, `verify_access.py`, and `docs/evidence/step10c-access-review.json`. IAM deployment access can change those six roles' policies, so apply only the reviewed Terraform source.

## 2. Capacity and spending review

Measured cluster allocatable capacity: **3,860 millicores, 6,585 MiB, 34 Pod slots**. Existing system Pods: eight. Eight API replicas plus seven worker Pods fit the aggregate requests. The model includes four simultaneous API surge Pods and one verification Job: **2,150 millicores, 2,700 MiB and 28 slots**, including existing system requests. Scheduling and actual memory usage still need live verification. Workers use Recreate updates; APIs use rolling updates. No worker node autoscaler or extra EC2/RDS/NAT/load balancer is introduced.

Keep the **USD 75 allowance** and **25 October 2026, 6 PM Asia/Colombo** cleanup target. The foundation model is USD 52.41; reserve USD 2 for light demonstration messaging, encryption requests, image storage and network usage, giving a USD 54.41 planning model before exclusions. This reserve is an assumption, not a live bill, AWS quote or hard cap. Taxes, retained artifacts and traffic vary. Later public hosting/controller/BI stages need another cost review. Queue long polling limits idle requests. SNS publisher KMS permissions follow [AWS's encryption-key guidance](https://docs.aws.amazon.com/sns/latest/dg/sns-key-management.html).

## 3. Owner CloudShell: prepare and apply the reviewed policy

After explicit approval, upload `.local/deployment/step10c-access.zip` through CloudShell Actions. Compare its SHA-256 with `docs/evidence/step10c-access-bundle.json`, then:

```bash
aws sts get-caller-identity
sha256sum step10c-access.zip
step10c_dir=$(mktemp -d "$HOME/wonderland-step10c-bundle.XXXXXX")
unzip step10c-access.zip -d "$step10c_dir"
bash "$step10c_dir/apply-access-cloudshell.sh" --prepare
```

Preparation checks the account, permission set, policy hashes and existing inline policy, validates the new policy and checks for a conflicting existing managed policy. It does not change access.

After the reviewed access approval:

```bash
bash "$step10c_dir/apply-access-cloudshell.sh" --apply
```

This creates the exact customer-managed policy, attaches its **customer-managed policy reference** and reprovisions account `708919751353`. Do not enter this account-owned policy ARN under AWS-managed policies. No keys/passwords are created, and no infrastructure is deployed by this helper.

## 4. CLI: apply only the reviewed event/IAM plan

From `D:\Courses\Microservices`:

```powershell
. ./scripts/aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
./scripts/deploy-cloud-workloads.ps1 -ApplyInfrastructure
```

The runner checks chamindu's account/role and the saved binary plan/source checksums, then applies the reviewed plan. It exports only non-secret topic ARNs, queue URLs and role ARNs. If the reviewed plan becomes stale, regenerate it and inspect the changes before applying. Do not replace it with an unreviewed auto-approved plan.

## 5. Build, push and deploy the private application

```powershell
./scripts/deploy-cloud-workloads.ps1 -Deploy
```

The runner builds five Linux/amd64 images using a pinned Python base and pinned dependencies, uploads unique immutable tags and resolves ECR digests. Docker's temporary login configuration is removed afterward. Helm references only digests and the five precreated runtime Secret names; credentials never appear in values files or Terraform.

The release is **wonderland**, namespace **wonderland**:

| Workload | Replicas | Database | AWS permission |
| --- | ---: | --- | --- |
| catalog, booking, payment, admission APIs | 2 each | Own service only | None |
| booking-maintenance | 1 | Booking | None |
| catalog-publisher | 1 | Catalog | Publish catalog topic |
| booking-publisher | 1 | Booking | Publish booking topic |
| admission-publisher | 1 | Admission | Publish admission topic |
| booking-prices | 1 | Booking | Receive/delete only pricing queue |
| analytics-bookings | 1 | Analytics | Receive/delete only booking analytics queue |
| analytics-admissions | 1 | Analytics | Receive/delete only admission analytics queue |

Pod Identity uses short-lived credentials. Kubernetes API token mounting stays disabled for these application Pods, following [EKS guidance](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html). The Pod Identity token is injected separately. No static AWS credentials or development profiles are mounted.

All Pods run without root, with a read-only root filesystem, dropped capabilities, bounded memory/CPU and temporary storage. API probes check liveness/readiness. Worker probes check a progress marker refreshed after successful loop activity, not just process existence. A healthy progress marker alone does not prove the outbox has no failed messages; inspect outbox counts, queue depth and DLQs as well. Per-process database pools are capped at four connections, keeping steady-state upper bounds around 60 across 15 application Pods before probes/surge.

## 6. Initialize and verify pricing before projection mode

The runner starts with Booking's HTTP pricing fallback. It queues current Catalog prices transactionally using `app.event_worker snapshot`. Catalog's relay publishes, SNS fans out to the pricing SQS queue, and Booking commits a versioned projection before acknowledging messages.

A temporary private verification Job compares all pricing fields/versions between Catalog and Booking, verifies API readiness and unauthenticated denials, and checks database TLS. It receives only the Catalog and Booking runtime Secret references for this explicit comparison and uses Catalog publisher's existing role to replay a previously published price event twice. Verify that one inbox row remains and the live consumer logs acknowledge `duplicate=True` for that event ID. Remove the verification Job and ConfigMap after exporting its sanitized report.

The verification script uses Python's standard HTTP library and explicitly sets `PYTHONPATH=/app` to import the production image's shared event package. Admission's image includes both that package and the RDS CA bundle. These packaging checks were repaired before final verification; no new production HTTP dependency was added.

Only after that passes does the runner set `pricingMode: projection` and wait for the final Helm rollout, then repeat verification. ConfigMap checksums cause Pods to restart on configuration changes. `frontendOrigin` remains empty and CORS origins are `[]` during this private rollout; use the actual HTTPS origin in 10D.

## 7. Admission delivery, retry and DLQs

Admission already records guest/ride facts and its outbox in the same transaction. Its new publisher uses that existing outbox and strips `user_sub` from the analytical payload. Analytics consumes its own SQS queue and commits its inbox plus arrival/ride facts together. It never receives Admission's database credential. The direct-database local pipeline remains available for the local development workflow but is not deployed to EKS.

SNS may accept a publish whose response is lost. Retries retain the same event ID; consumer inbox hashes suppress duplicates and reject reuse with different content. Invalid facts roll back the inbox and are left unacknowledged. SQS visibility is 60 seconds and processing redrive is five receives. Separate delivery DLQs catch SNS-to-SQS delivery failures. Do not claim a local fault test proves AWS redrive behavior; capture live DLQ evidence separately during rollout/reliability rehearsal.

Read-only operator checks:

```powershell
& ./.local/tools/kubectl.exe --kubeconfig .local/deployment/kubeconfig -n wonderland get deployments,pods,services
& ./.local/tools/kubectl.exe --kubeconfig .local/deployment/kubeconfig -n wonderland logs deployment/wonderland-booking-prices --since=10m
& ./.local/tools/terraform/terraform.exe '-chdir=infra/terraform/workloads' output -json
```

Use queue metadata to inspect approximate visible/in-flight counts. Do not purge queues or automatically redrive poison messages. Record failed event IDs and causes; use the scoped publisher's `status`/`requeue` commands only after fixing the cause. Outbox events stop automatic publication after ten failures and require deliberate requeue.

## 8. Failure handling, rollback and cleanup

Do not run migrations inside every API replica. Step 10B completed all required migration heads; this stage needs no schema migration. A failed readiness probe should lead to sanitized Pod logs, image/permission checks and a reviewed repair, without printing database URLs or Secret YAML. If projection initialization fails, keep HTTP pricing mode until repaired. A later bad Helm release can be rolled back to a verified revision; do not roll back to the disabled placeholder chart and assume service availability.

During the agreed one-week teardown, export reports/logs and inspect outbox/queues before deleting event infrastructure. Uninstall application/verification Helm resources first, then destroy `infra/terraform/workloads`, then follow foundation teardown. The runtime Kubernetes Secrets belong to Step 10B, so Helm uninstall does not erase them. Keep the agreed final RDS snapshot, state and 14-day image review package. Never delete the existing Cognito or older development messaging stack as a shortcut. The deployment customer-managed policy should be detached/reviewed once workload teardown is confirmed; owner access changes are deliberate setup actions.

## 9. Validation status and remaining scope

Completed before cloud mutation: all five service images built locally; eight policy/chart tests passed; a mocked Terraform boundary test passed; Access Analyzer returned zero findings; Terraform validated and produced 45 additions only. Isolated PostgreSQL tests passed twice-run bootstrap/seed/credential checks plus ambiguous publication retry, same-ID replay deduplication, removal of visitor identity, tampering rejection and rollback of invalid fact inboxes.

Completed in AWS: owner-provisioned scoped deployment policy, reviewed `/32` endpoint repair, 45 managed event/IAM resources, five digest-pinned images, six exact worker role associations, eleven ready Deployments and fifteen ready application Pods. Both HTTP-fallback and projection-mode smoke checks passed: four pricing tiers matched Catalog; repeated event delivery retained one inbox row and produced duplicate acknowledgements. All four APIs passed readiness and unauthenticated-denial checks. Catalog and Booking live TLS checks passed. The three outboxes had no pending/failed events, the three processing queues had no observed backlog, and all six DLQs were empty at verification. Empty DLQs do not demonstrate poison-message redrive.

The verification Job, Pod and ConfigMap were removed. No new worker nodes, RDS instances, NAT gateways or load balancers were created. Both Terraform roots report no changes, and the new workload state is encrypted/versioned in S3. Temporary Docker authentication files were removed.

For repeat read-only verification:

```powershell
. ./scripts/aws-common.ps1
& ./.venv/Scripts/python.exe scripts/verify_cloud_workloads.py
```

The common script exposes the bundled AWS CLI to kubectl's credential helper in the current process. Keep the five Kubernetes runtime Secrets private; the verifier prints only metadata/counts and booleans.

Remaining: live invalid-message redrive, authenticated booking/payment/admission flows, actual billed-cost review, internal-hop TLS decisions, UI hosting and cloud Metabase need their later-stage evidence. Booking/Admission event infrastructure and consumers are deployed and healthy, but this stage's real published business events were Catalog pricing snapshots; it did not fabricate purchases or arrivals to imply a completed hosted walkthrough. Do not mark the full assignment complete from this milestone.
