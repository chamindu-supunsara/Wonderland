# Step 10A: foundation costs and AWS permissions

Status: **foundation permissions and the subsequently approved infrastructure are deployed and verified**. This document records the earlier access workflow. Account `708919751353`, Mumbai `ap-south-1`, profile `wonderland-feasibility`. See [actual deployment results and cleanup timing](10-foundation-deployment.md). Checkout, admission and analytics remain mock; no application endpoint was changed.

The state bucket is already deployed under the earlier state-only approval. The next foundation plan has **56 additions, zero changes and zero deletions**. This guide prepares its access; the previous Step 9 test approval and state-only approval do not authorize this foundation apply.

## 1. Review the one-week cost

Regional Price List rates were checked on 18 October 2026. Seven days means 168 running hours; monthly storage and secrets are prorated using the same 730-hour comparison model.

| Component | Configuration | Seven-day core model, USD |
|---|---|---:|
| EKS | One standard-support control plane | 16.80 |
| Workers | Two On-Demand t3.medium instances | 15.05 |
| NAT gateway | One zonal gateway | 9.41 |
| PostgreSQL | One Single-AZ db.t4g.small | 7.06 |
| NAT public IPv4 | One address | 0.84 |
| Worker disks | 40 GB gp3 total | 0.84 |
| Database storage | 20 GB gp3 initially | 0.60 |
| Secrets | Five service containers plus RDS master | 0.55 |
| **Total before exclusions** | **168 hours** | **51.15** |

The unrounded aggregate determines the total; rounded rows can differ by a cent. The comparable model is **USD 0.3045/hour**, **USD 7.31/day**, or **USD 222.27/730 hours**. These are estimates, not actual billing or a spending cap. Credits/Free Tier balances are not assumed.

Allow additional money for NAT processing (USD 0.056/GB), transfer/cross-AZ traffic, CPU credits, CloudWatch, ECR/scanning, S3, additional backups, storage growth, taxes and existing account services. RDS can grow storage to 40 GB. Provisioning and deletion time can also be billable. Later ALB, API Gateway, Amplify and hosted Metabase are outside this estimate; ALB alone has a USD 0.0239/hour base before usage. Re-estimate when adding them.

One NAT and Single-AZ RDS are shared failure points. Two workers do not make the entire platform highly available. See the [full cost review and source evidence](10-foundation-cost-review.md).

## 2. Review the permission change

Deploy through the non-root **WonderlandFeasibility** permission set assigned to `chamindu`. Use an owner/authorized Identity Center administrator session only to change that permission set. No long-lived access keys are required.

The reviewed [operator-policy.json](../../infra/terraform/foundation/operator-policy.json) was merged as an **addition** to the existing inline policy on 18 October 2026 after explicit permission approval. AWS-managed `arn:aws:iam::aws:policy/ReadOnlyAccess` remains attached and supplies inventory reads, including KMS key descriptions. Do not substitute an account-local policy ARN or replace the current inline policy with just this addition.

| Scope | New permissions and purpose |
|---|---|
| EKS `wonderland-demo` | Create/delete cluster, application node group, access entries and Pod Identity agent; update cluster configuration; associate/disassociate access policies; tags |
| IAM `wonderland-demo-cluster`, `wonderland-demo-nodes` | Create/delete/tag these roles; attach/detach only four named EKS/CNI/ECR AWS-managed policies; pass these roles to EKS/EC2 |
| Mumbai NAT and Elastic IP | Allocate/release addresses and create/delete NAT gateways; **regional Resource `*`**, not limited to future resource IDs |
| RDS `wonderland-demo` | Create/modify/delete instance, subnet group and prefixed parameter groups; parameter changes/tags; create prefixed final snapshot; use default PostgreSQL 16 option group |
| Application secrets `wonderland-demo/*` | Create/tag/untag containers; deletion requires at least seven days of recovery |
| RDS-generated secrets `rds!db-*` | Create/tag generated secret; its name is unknown before creation |
| ECR `wonderland-demo/*` | Create/delete/tag repositories and configure immutable tags/scanning; image push rights come later |
| CloudWatch `/aws/eks/wonderland-demo/cluster` | Create/delete/tag this group and manage retention |
| RDS service-linked role | Create only the standard RDS service-linked role, if needed, for `rds.amazonaws.com` |

ECR and application-secret grants also cover additional names under their project prefixes. The RDS secret prefix covers generated RDS names in this account/region. EKS grants allow access administration within the demo cluster, including cluster administrator access. These deployment privileges are separate from Cognito application administrator membership.

This covers initial creation and reviewed cleanup operations, not every future upgrade, restore, image upload or DB bootstrap. Later changes need their own scoped review. There is no new `GetSecretValue`, `PutSecretValue`, arbitrary policy creation, user creation or Identity Center administration grant. `CreateSecret` can include an initial value; this Terraform plan creates empty service containers. RDS manages its master secret. No password values are read in this preparation.

**Existing access remains broad:** Step 9 left Mumbai-wide EC2 lifecycle/instance operations, ELB operations and regional API Gateway paths in this permission set. The merge preserves these and the state-bucket grants. This addition is not a permissions boundary and does not make the effective role project-only. Removing old grants or switching to a dedicated permission set would be a separate access change.

## 3. Repeat the read-only local review

From PowerShell in `D:\Courses\Microservices`:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
& .\.venv\Scripts\python.exe scripts/review_foundation_permissions.py
```

Expected account: `708919751353`; role starts `AWSReservedSSO_WonderlandFeasibility_`. If expired, run `& $LocalAws sso login --profile wonderland-feasibility` and complete authorization directly in AWS.

The review checks the inline-policy fingerprint, attached ReadOnlyAccess, saved create-only plan and absence of the target cluster/database. It validates the combined policy using AWS Access Analyzer. It performs no permission change, secret-value access, infrastructure apply or paid Cost Explorer query.

Recorded result: **13 new statements; merged policy 9,830 bytes; Access Analyzer zero findings**. The Identity Center non-whitespace inline limit is 10,240 bytes; only 410 compact bytes remain. The helper stops on drift or oversize rather than dropping permissions. See [machine-readable review](../evidence/step10-foundation-permissions.json).

Validation does not simulate every downstream call, guarantee quotas or prove apply will succeed. After permission approval/provisioning, verify the effective role again.

## 4. Prepare owner CloudShell without changing access

The bundle `.local/deployment/step10-foundation-permissions.zip` contains `operator-policy.json`, `merge_operator_policy.py`, and `prepare-permissions-cloudshell.sh` from the **foundation** directory. Do not use the older bootstrap or Step 9 helpers.

1. Open Mumbai CloudShell using an owner/authorized Identity Center administrator setup session. Enter passwords/MFA only in AWS.
2. Verify the ZIP checksum against [bundle evidence](../evidence/step10-foundation-permission-bundle.json). Locally: `Get-FileHash .local/deployment/step10-foundation-permissions.zip -Algorithm SHA256`.
3. Upload that ZIP using CloudShell **Actions → Upload file**. Extract into a fresh directory:

```bash
aws sts get-caller-identity
foundation_review_dir=$(mktemp -d "$HOME/wonderland-foundation-review.XXXXXX")
unzip -q "$HOME/step10-foundation-permissions.zip" -d "$foundation_review_dir"
bash -n "$foundation_review_dir/prepare-permissions-cloudshell.sh"
set -o pipefail
bash "$foundation_review_dir/prepare-permissions-cloudshell.sh" --prepare 2>&1 | tee "$foundation_review_dir/prepare.log"
```

Expected final line: `PREPARED ONLY: no permissions changed and no infrastructure deployed.` The helper checks account/permission-set identity, validates the pinned proposal, preserves existing statements, checks size and runs Access Analyzer. It retains a separate backup/evidence directory and prints its path. With no option it also defaults to preparation only.

**Completed on 18 October 2026:** uploaded the checksum-verified ZIP to owner CloudShell in account 708919751353, extracted into `/home/cloudshell-user/wonderland-foundation-review.joRi4t`, passed Bash syntax checking and ran `--prepare` successfully with exit code 0. The merged policy is 9,830 bytes with zero Access Analyzer findings. Backup/validation files are in `/home/cloudshell-user/wonderland-foundation-permissions.eJYkA8`; the execution log is `prepare.log` in the review directory. [Recorded result](../evidence/step10-foundation-cloudshell-preparation.json) and [screenshot](../evidence/step10-foundation-cloudshell-prepared.png). No access change or infrastructure deployment occurred. Keep using the non-root SSO profile for eventual deployment.

On error, retain the exact output and stop. Do not substitute AdministratorAccess or discard statements. A changed baseline needs a fresh review. After a shell restart, use the actual extracted directory rather than guessing a path.

## 5. Apply permissions only after their review and approval

This later **permission change** is separate from approving billable infrastructure. It updates the inline policy and reprovisions only account 708919751353; it creates no EKS/RDS/NAT resources.

After explicit approval for this policy, in the same owner session:

```bash
set -o pipefail
bash "$foundation_review_dir/prepare-permissions-cloudshell.sh" --apply 2>&1 | tee "$foundation_review_dir/apply.log"
```

Expected final line: `SUCCEEDED: reviewed foundation permissions provisioned; no infrastructure deployed.` Keep the backup and request ID. A timeout means **pending**, not success: inspect the request before retrying. If the inline update succeeds but provisioning fails, the permission-set definition and account role can differ; diagnose and reprovision rather than assuming a rollback.

Return to local PowerShell, renew the non-root SSO session if needed, and rerun `scripts/review_foundation_permissions.py`. It accepts the original baseline or identical already-merged policy. Compare effective grants with the reviewed proposal before advancing.

**Completed on 18 October 2026:** owner CloudShell ran the checksum-verified helper with `--apply`, returned exit code **0**, and provisioned account 708919751353 successfully. Request ID: `e97d2e7c-d69f-4eb5-8598-72aeb6d440c1`. Backup/validation directory: `/home/cloudshell-user/wonderland-foundation-permissions.s3dfKh`. Log: `/home/cloudshell-user/wonderland-foundation-review.joRi4t/apply.log`. The commands above document reproduction; do not repeat a completed update unnecessarily.

Non-root CLI verification found the exact reviewed merged policy SHA-256 `1cb5017593ad6b19334967a11b0f843c814578fc4ab5fd5ac480106c4c6e91c9`, preserved all old grants and ReadOnlyAccess, and returned zero Access Analyzer findings. The existing CLI session was valid; no login renewal was needed. An EC2 `AllocateAddress` request with `DryRun=True` returned **DryRunOperation** as expected, proving that authorization check passed **without allocating an address**. See [AWS's DryRun contract](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_AllocateAddress.html).

For a manual repeat of that specific non-mutating check:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws ec2 allocate-address --domain vpc --dry-run --region ap-south-1 --profile wonderland-feasibility
```

AWS CLI reports `DryRunOperation` as an error/nonzero exit even when authorization succeeds. Keep `--dry-run`; do not remove it to obtain an exit code of zero. `UnauthorizedOperation` means the permission check failed. This checks one action, not every downstream service call or quota. [Provisioning record](../evidence/step10-foundation-permissions-applied.json), [CLI verification](../evidence/step10-foundation-cli-verification.json), and [screenshot](../evidence/step10-foundation-permissions-applied.png).

Live reads still show no `wonderland-demo` EKS cluster or RDS instance. The saved plan remains 56 create-only additions; it has not been applied.

## 6. Refresh the plan before separate billable approval

The [fresh quota and plan walkthrough](10-pre-deployment-checks.md) is now completed for 18 October 2026: **17 quota checks and 4 availability checks passed**, and the regenerated plan has **56 additions, no changes or deletions**. The Standard On-Demand quota is now **16 vCPUs**, with zero current usage and four planned worker vCPUs; the older five-vCPU reading is superseded. Planned zones and encrypted PostgreSQL 16/db.t4g.small gp3 orderability are verified. Refresh these point-in-time checks again if conditions change. Default managed-node upgrades can surge instances; future upgrades need quota headroom and another review.

```powershell
.\scripts\plan-deployment-foundation.ps1
```

Read the regenerated plan: expect 56 additions, no changes/deletions, a private encrypted DB, two t3.medium workers, one NAT, seven-day cluster log retention, deletion protection and a final snapshot. Recheck the operator's current `/32` API allowlist. Review any material change; never apply an old binary merely because its count matches.

Before **separate billable apply approval**, record the start and seven-day cleanup date/time in Asia/Colombo, a spending allowance including variable/later-platform costs, and artifact retention decisions. No date is scheduled because deployment has not started. An AWS Budget alert is not a hard cap; none has been created here.

No Terraform apply is executed here. After permission verification and billable approval, apply only the fresh reviewed binary under `wonderland-feasibility`, monitor creation and verify resources. Follow [the staged cloud guide](10-cloud-deployment.md) for DB bootstrap, workload IAM/images, routing/frontend and hosted analytics. Foundation creation alone does not host the application.

## 7. Plan end-of-week cleanup

Inspect a Terraform destroy plan before deletion. Disable RDS deletion protection through a deliberate reviewed change; keep `skip_final_snapshot=false` and retain the final snapshot. Do not force-empty ECR or purge secret recovery windows. ECR `force_delete=false` blocks deletion while images remain; decide image retention first.

Delete application/edge resources before network/database dependencies. Verify cluster, node groups/instances/disks, RDS, NAT, EIP, load balancers and interfaces afterward. S3 state/version history is intentionally retained; snapshots and other retained artifacts may continue charging. Pending-deletion secrets reserve their names during recovery; do not blindly recreate them.

Stopping workers alone leaves EKS and NAT charges running. Stopping RDS is not complete cleanup. Review Billing after usage posts; this preparation does not establish final charges or schedule automatic cleanup.

## Official references

- [EKS pricing](https://aws.amazon.com/eks/pricing/) and [VPC pricing](https://aws.amazon.com/vpc/pricing/).
- [RDS managed-password permissions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html).
- [EKS actions/scopes](https://docs.aws.amazon.com/service-authorization/latest/reference/list_eks.html), [RDS actions/dependencies](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rds.html), and [Secrets Manager recovery conditions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_secretsmanager.html).
- [Identity Center quotas](https://docs.aws.amazon.com/singlesignon/latest/userguide/limits.html).
