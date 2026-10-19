# Step 10A: approved billable foundation deployment

## Scope and actual start

**Completed and verified:** Terraform added **56 resources**, changed/destroyed none, and all **23 live checks passed**. Both nodes are Ready; eight system pods are healthy; RDS PostgreSQL **16.13** is available, private and encrypted. The fresh post-apply plan reports **no changes** and S3 foundation state is encrypted/versioned. Apply finished **18 October 2026 at 2:03:26 PM, Asia/Colombo**. The application is not yet deployed.

The user approved the reviewed **56-resource** foundation plan within the **USD 75** allowance and agreed retention/cleanup plan. When informed that it was earlier than the proposed 6 PM start, the user explicitly chose **deploy now, keep the cleanup deadline**.

Apply started **18 October 2026 at 1:52:45 PM, Asia/Colombo** (08:22:45 UTC), using non-root `wonderland-feasibility` in account `708919751353`, Mumbai. Cleanup remains targeted to start **25 October at 6:00 PM, Asia/Colombo**. That is approximately **172.12 hours** from actual apply start; the same unrounded core model estimates **USD 52.41**, before usage, taxes, retention and deletion time. This is not the measured bill or a hard cap.

Checkout remains mock. This deployment is foundation only: no application images, database schema bootstrap, Helm workloads, API Gateway route, Amplify frontend or hosted Metabase is deployed by the 56-resource plan.

Current execution status and final verification are recorded in [deployment evidence](../evidence/step10-foundation-deployment.json). While that record says apply is running or verification pending, do not assume all resources are healthy. No automatic cleanup, AWS Budget or billing cap has been created.

## 1. Final checks completed before apply

The final read-only checks reverified:

- Account and exact non-root SSO role, effective reviewed inline policy and attached ReadOnlyAccess.
- Zero AWS Access Analyzer findings.
- All 17 checked quotas and four availability checks, including 0+4 worker vCPUs against the current quota of 16.
- Target foundation absent before creation; EKS 1.35 standard support and compatible encrypted PostgreSQL 16/db.t4g.small gp3 offerings in both planned zones.
- Approved binary/source fingerprints and current operator IPv4 `/32` match; no source or network change required regeneration.

Applied binary SHA-256:

```text
f4823239e9fea28015359546df6ce3577ee6905609575fc1238bcbf0c399b528
```

See [fresh readiness](../evidence/step10-foundation-readiness.json), [plan summary](../evidence/step10-foundation-plan.json), [effective policy verification](../evidence/step10-foundation-permissions.json) and [spending/retention record](../evidence/step10-spending-cleanup-retention.json).

## 2. Apply the approved saved plan

This documents the command already started; do not rerun the old saved plan after state has changed:

```powershell
. .\scripts\aws-common.ps1
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:AWS_SDK_LOAD_CONFIG = '1'
& .\.local\tools\terraform\terraform.exe -chdir=infra/terraform/foundation apply -input=false -no-color "$PWD\.local\deployment\foundation.tfplan"
```

The execution also enforced the exact saved-plan fingerprint and rejected unexpected environment credentials before apply. Live output is retained in `.local/deployment/foundation-apply.log`; process completion is recorded in `.local/deployment/foundation-apply-result.json`. Never commit raw plans, state, actual variables or local credentials.

EKS, RDS and managed worker creation take time. Terraform can create independent networking/storage resources while managed services are still provisioning. A partial failure can leave billable resources: inspect the exact error and current state, then plan a reviewed continuation. Do not blindly rerun a stale binary, replace permissions with AdministratorAccess, or destroy retained artifacts to get past an error.

## 3. Verify AWS resources and Kubernetes access

After apply succeeds:

```powershell
.\scripts\verify-deployment-foundation.ps1
```

This writes Terraform outputs and kubeconfig only under ignored `.local/deployment/`. It does not overwrite the normal user kubeconfig. It waits for worker readiness and cluster DNS, saves read-only `kubectl` snapshots, then runs `scripts/verify_foundation_deployment.py`.

The live verifier checks EKS/managed-node/Pod Identity health, explicit SSO cluster-admin access, two private t3.medium workers, IMDSv2, no automatic public IPs on compute subnets, one available NAT, private/encrypted RDS PostgreSQL, deletion protection/backups, active RDS-managed master-secret metadata, `rds.force_ssl=1`, immutable/scanned ECR repositories, empty service-secret containers, existing Cognito IDs and mock checkout configuration. **It never retrieves a database password.**

Node/pod readiness proves cluster foundations, not application health. Database metadata and a required-TLS parameter do not prove a successful application TLS connection; that needs the private DB bootstrap stage. Final snapshots and restores still require a recovery rehearsal.

## 4. Confirm Terraform has no remaining changes

After live verification, run a fresh normal plan with `-detailed-exitcode`. Exit **0** means no changes; **2** means drift/proposed changes that require review; **1** means a planning error. Save the post-apply plan separately from the original approved artifact:

```powershell
. .\scripts\aws-common.ps1
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:AWS_SDK_LOAD_CONFIG = '1'
& .\.local\tools\terraform\terraform.exe -chdir=infra/terraform/foundation plan -input=false -detailed-exitcode -no-color "-out=$PWD\.local\deployment\foundation-post-apply.tfplan"
```

Record state resource count, remote backend persistence, live verification and the post-apply exit code in deployment evidence before declaring Step 10A verified. Do not print state contents or secret values into a public report.

The first post-apply plan found one metadata-only difference: AWS returned `apply_method=pending-reboot` for the existing `rds.force_ssl=1` parameter while Terraform defaulted to `immediate`. Live metadata showed the parameter group **in-sync**. Made the apply method explicit in `database.tf`, matching the existing AWS state; no second cloud apply or reboot ran. Terraform formatting/validation and all five foundation mock cases passed, then a fresh normal plan returned exit **0** with 56 managed resources and no differences. This preserves TLS-required behavior. [AWS SSL guidance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html).

Final evidence: [23 live checks](../evidence/step10-foundation-live-verification.json), [zero-drift and state verification](../evidence/step10-foundation-post-apply.json), and [deployment execution](../evidence/step10-foundation-deployment.json). The original approved plan/source fingerprints remain historical evidence; current source fingerprints and the normalization are recorded separately.

## 5. Cost, retention and next lesson

The **USD 75** allowance and manual review thresholds remain in effect. Actual costs are delayed and have not been established by a successful apply. Keep cleanup fixed at **25 October, 6 PM** unless the user explicitly revises it. [Agreed staged cleanup/retention](10-spending-cleanup-retention.md) keeps state and retains the final snapshot/release images for 14 days after actual teardown; application-secret deletion uses seven-day recovery. No deletion has been scheduled merely by deploying.

Next is **10B: private database bootstrap, separate service roles/credentials, TLS CA configuration, migrations and seed data**. Then continue images/workload IAM/messaging, routing/Angular hosting and hosted analytics. Do not point the local application at unfinished cloud resources or replace mock checkout with a payment provider during this milestone.
