# Step 10A: agreed allowance, deployment window and retention

**Foundation deployment approved, completed and verified on 18 October 2026.** The user chose immediate deployment instead of the original 6 PM target. Actual apply started **1:52:45 PM** and finished **2:03:26 PM**; cleanup remains **25 October at 6 PM**. Account `708919751353`, Mumbai `ap-south-1`. All times below are **Asia/Colombo (UTC+05:30)**. Checkout remains mock. [Deployment results](10-foundation-deployment.md).

## 1. Spending allowance: USD 75

You selected **USD 75** for the incremental foundation trial, cleanup and retained artifacts. The core 168-hour model is **USD 51.15**, leaving **USD 23.85** of nominal headroom. Usage, taxes, provisioning/deletion time, retained snapshots/images and other trial costs must fit that headroom. Existing account charges are separate. Later ALB/API Gateway/Amplify/hosted analytics additions need an updated estimate and scope review; this record does not preapprove them.

This is a planning allowance, **not an AWS-enforced cap**. No credit balance is assumed, and no actual bill was queried for this decision. See [cost inputs and exclusions](10-foundation-cost-review.md).

The approved earlier start makes the actual-start-to-cleanup model **172.12 hours / USD 52.41**, leaving **USD 22.59** nominal headroom. Actual charges have not been established; the original 168-hour figure remains a comparison model.

Use these manual review thresholds:

| Threshold | Planned response |
|---|---|
| USD 60, or forecast likely to exceed USD 75 | Review usage, remaining days and retained storage; consider earlier cleanup |
| Before further spending scope or a longer runtime | Obtain a revised allowance or a reviewed cleanup decision |
| USD 75 | Do not approve additional billable scope without a revised allowance; running resources can still accrue charges until cleanup finishes |

These thresholds are recorded instructions, not configured alerts. No AWS Budget, notification recipient, budget action, account spending restriction or scheduled shutdown has been created. AWS notes that budget notifications can lag incurred charges; an alert would still not be a guaranteed cap. [AWS Budgets guidance](https://docs.aws.amazon.com/cost-management/latest/userguide/bcm-lite-use-budget.html).

## 2. One-week target window

| Milestone | Sri Lanka time |
|---|---|
| Actual deployment start (approved override) | **Sunday, 18 October 2026, 1:52:45 PM** |
| Pre-cleanup review and evidence preparation | **Saturday, 24 October 2026, 6:00 PM** |
| Start cleanup | **Sunday, 25 October 2026, 6:00 PM** |
| Provisional application-secret recovery boundary | **Sunday, 1 November 2026, 6:00 PM**, if deletion is scheduled at the target cleanup time |
| Provisional snapshot/image retention review | **Sunday, 8 November 2026, 6:00 PM**, subject to actual teardown completion |

The original 6 PM start and cleanup targets were 168 hours apart. The approved actual start was earlier, giving approximately **172.12 hours** to cleanup. No scheduled task or automatic deletion exists.

Record the actual provisioning start and actual teardown completion when they happen. Cleanup begins at the selected deadline and takes time; charges can continue while services are deleting. Fourteen-day artifact retention runs from **actual teardown completion**, so move the provisional November review date later if necessary. AWS secret deletion timing is based on when the deletion request is accepted and is not guaranteed to complete at the displayed boundary.

If deployment approval or setup misses the target start, agree a revised window before proceeding. Do not silently extend cleanup or claim the full week was available. Selecting these dates does not approve deployment or authorize an unattended destroy.

## 3. Selected 14-day recovery package

| Artifact | During runtime | At later approved cleanup | After cleanup |
|---|---|---|---|
| Terraform state | Existing protected, encrypted/versioned S3 storage | Keep bucket and state history | Retain until a separate project-close review; storage/requests can continue charging |
| RDS database | Private/encrypted; seven-day automated backups; deletion protection enabled | Deliberately review disabling protection, create final encrypted snapshot and delete DB | Keep final snapshot for **at least 14 days** after teardown, then review deletion |
| RDS automated backups | Seven-day rolling retention | Current plan has `delete_automated_backups=true` | No additional retained-automated-backup policy selected; final snapshot is the post-teardown recovery artifact |
| ECR release images/repositories | Immutable release tags/digests; no force deletion | Keep referenced release digests **and their repositories** | Retain **14 days** after teardown, then review image/repository cleanup |
| Five application-secret containers | No values in Terraform; seven-day recovery setting | Schedule deletion with **seven-day recovery**, never force purge | Recover if needed before AWS's deletion deadline; names remain reserved while pending deletion |
| RDS-managed administrator secret | Managed by RDS | AWS deletes it with the DB | Not covered by the application-secret recovery promise; restore needs reviewed credential setup |
| Logs and assignment evidence | Cluster log retention is seven days while its group exists | Export required evidence before deleting groups | Keep exported evidence locally for assignment and recovery review; no local evidence deletion scheduled |

Manual/final RDS snapshots do not expire merely because a 14-day intention was recorded, and they can continue charging until deleted. [AWS snapshot guidance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DeleteSnapshot.html). RDS removes its managed administrator secret with the DB; a final snapshot is not a promise that the original credentials remain available. [AWS managed-secret lifecycle](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html).

The selected package provides a recovery artifact; a restore rehearsal is still pending. Restoring creates another billable database, needs suitable network/access configuration and reviewed master/application credential setup. Do not claim tested recovery until that rehearsal succeeds.

## 4. Cleanup must follow a reviewed staged plan

Keeping ECR images also keeps their repositories. **A blanket `terraform destroy` is not suitable for this retention package:** `force_delete=false` blocks deletion of populated repositories. Prepare a staged teardown that removes runtime resources while preserving the selected ECR resources and their Terraform state entries. Later, review a separate image/repository deletion plan after the retention period. Do not force-empty ECR, remove ownership records or change retention safeguards merely to make destroy pass.

At the pre-cleanup checkpoint:

1. Export the walkthrough, plan outputs, selected logs and image-digest manifest. Avoid copying credentials into evidence.
2. Verify the DB snapshot naming/recovery plan and intended ECR digests. Inventory dependencies and any later platform resources.
3. Review the teardown plan and its deletion-protection change, retained resources and expected final snapshot. Confirm destructive steps at execution time.
4. Stop application/worker/edge dependencies in the reviewed order, then remove EKS workers/control plane, DB, NAT and EIP as planned. Preserve the state bucket and selected artifacts.
5. Verify deletions have completed, including instances/disks, load balancers and interfaces. Terraform-owned cluster logs are removed with their group; RDS-created groups need a separate inventory and scoped cleanup review.
6. Record actual completion, retained snapshot IDs/image digests, secret deletion dates and the revised 14-day artifact review date. Check Billing after usage posts.

The present foundation operator grant does not include deleting final RDS snapshots or pushing/deleting images in the new repositories. Any extra artifact-cleanup permissions must be reviewed separately. This planning step adds no access and performs no cleanup.

## 5. Approved foundation and next checkpoint

The selected allowance, window and retention are recorded in [machine-readable evidence](../evidence/step10-spending-cleanup-retention.json). The current reviewed binary plan SHA-256 is:

```text
f4823239e9fea28015359546df6ce3577ee6905609575fc1238bcbf0c399b528
```

That plan was applied: **56 added, none changed/destroyed**. A post-apply source normalization makes the TLS parameter's apply method match existing AWS metadata; it required no cloud mutation/reboot. The fresh plan reports no changes, with deletion protection, final snapshot and secret recovery preserved.

Next is private DB bootstrap and application deployment stages. Re-estimate/review new billable scope and changed plans before later additions. Do not rerun the historical foundation binary. See [live verification and next lesson](10-foundation-deployment.md).

The approved foundation is running. No secret deletion, image purge, AWS Budget, reminder or automatic cleanup has been executed or scheduled.
