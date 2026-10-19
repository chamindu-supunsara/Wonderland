# Step 10A: fresh quotas and refreshed foundation plan

**Historical pre-deployment checks:** the user subsequently approved and completed this foundation deployment. All 23 live checks passed and the post-apply plan has no changes. See [the deployment guide](10-foundation-deployment.md). Inventory/quota usage below is the snapshot before creation, not current inventory after deployment.

Checked **18 October 2026**, Mumbai (`ap-south-1`), account `708919751353`, using the non-root `wonderland-feasibility` profile. **No deployment or quota increase was performed. Checkout remains mock.** Foundation permissions were provisioned in the previous milestone; infrastructure approval remains separate.

## 1. Fresh account quota and usage checks

Run from PowerShell in `D:\Courses\Microservices`:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
& .\.venv\Scripts\python.exe scripts/check_foundation_readiness.py
```

Expected account: `708919751353`, with the WonderlandFeasibility assumed role. Renew an expired session with `& $LocalAws sso login --profile wonderland-feasibility`; complete authentication directly in AWS.

The checker reads applied service quotas, current inventory, account RDS limits, IAM role usage and regional version/instance offerings. It makes no resource or quota changes. It must print `CHECKED_NO_DETECTED_QUOTA_BLOCKER`; inspect any error or `REVIEW_REQUIRED` result before proceeding. The public report is [step10-foundation-readiness.json](../evidence/step10-foundation-readiness.json). Raw inventory, which can contain network details, stays ignored under `.local/deployment/`.

All **17 quota comparisons** and **4 availability checks** passed:

| Capacity | Current usage | Planned addition | Applied limit |
|---|---:|---:|---:|
| Standard On-Demand vCPUs | 0 | 4 | **16** |
| Elastic IPs | 0 | 1 | 5 |
| VPCs in Mumbai | 1 | 1 | 5 |
| Internet gateways | 1 | 1 | 5 |
| NAT gateways in `ap-south-1a` | 0 | 1 | 5 |
| Subnets in the new VPC | 0 | 6 | 200 |
| Route tables in the new VPC | 0 | 4, including automatic main table | 200 |
| EKS clusters | 0 | 1 | 100 |
| Managed node groups in new cluster | 0 | 1 | 30 |
| Nodes in new managed group | 0 | 2 | 450 |
| gp3 EBS storage | 0 | 40 GiB | 50 TiB |
| RDS instances | 0 | 1 | 20 |
| RDS subnet groups | 0 | 1 | 20 |
| RDS parameter groups | 0 | 1 | 20 |
| RDS allocated storage | 0 | Up to 40 GiB | 100,000 GiB |
| RDS manual snapshots | 0 | Allowance for one final snapshot | 100 |
| IAM roles, account-wide | 16 | 3, including optional RDS service-linked role | 1,000 |

The old five-vCPU reading is superseded by the current **16-vCPU** account quota. Initial workers consume four, leaving twelve under the current inventory. No quota increase was requested by this workflow. This does not reserve capacity or authorize larger instances or extra workers. Future managed-node upgrades can launch extra nodes and need another cost/quota review.

Availability results:

- Planned zones are `ap-south-1a` and `ap-south-1b`; `t3.medium` is offered in both.
- EKS **1.35** is in **STANDARD_SUPPORT**. The current API reports standard support ending **27 March 2027**.
- Encrypted PostgreSQL **16**, class **db.t4g.small**, with gp3 storage is orderable in both zones. Returned minor versions range from 16.9 through 16.15. Terraform specifies major version 16, so AWS selects an available default minor; the plan does not pin a specific minor.
- Target foundation VPC, EKS cluster and RDS instance are absent from the queried inventory.

Quotas and offerings are point-in-time checks, not reservations or a guarantee of successful creation. Not every per-resource limit or later ALB/API Gateway/Amplify/worker quota is covered. Fifty-six is the number of Terraform-managed additions; AWS also creates dependent objects such as a default route table/security group and managed service infrastructure.

## 2. Regenerate the plan

```powershell
.\scripts\plan-deployment-foundation.ps1
```

This verifies account/non-root identity, resolves the permanent SSO role ARN, refreshes the current public IPv4 `/32`, initializes the S3 backend and runs **Terraform plan only**. It saves:

```text
.local/deployment/foundation.tfplan
.local/deployment/foundation-plan.json
.local/deployment/foundation-plan.txt
```

Actual result:

```text
Plan: 56 to add, 0 to change, 0 to destroy.
Foundation plan saved. No infrastructure apply was attempted.
```

The previous plan JSON is retained locally as `foundation-plan.before-refresh.json`. Review found the same 56 managed-resource addresses and **no differences in their planned values**. The refreshed binary has a new fingerprint because it is a new plan artifact; use the new artifact for any later approval.

Current binary SHA-256:

```text
f4823239e9fea28015359546df6ce3577ee6905609575fc1238bcbf0c399b528
```

The sanitized [plan summary](../evidence/step10-foundation-plan.json) records timestamps, source/plan hashes and safeguards. To inspect the full private plan locally:

```powershell
Get-Content .local/deployment/foundation-plan.txt
Get-FileHash .local/deployment/foundation.tfplan -Algorithm SHA256
```

Do not publish raw plan files or actual variables. They include the operator address and can contain sensitive values in future stages. Keep the committed examples and provider lock files; leave actual plans, state and credentials ignored.

## 3. Reviewed plan safeguards

The refreshed JSON was checked for:

- Exactly 56 managed creates, with no updates, replacements or deletes; same reviewed resource addresses.
- Two t3.medium workers; six subnets with automatic public IP assignment disabled; one NAT.
- EKS 1.35 standard support, private endpoint enabled and public API restricted to the refreshed operator `/32`; permanent SSO role ARN for access.
- Private, encrypted PostgreSQL 16; 20 GiB initially, maximum 40 GiB; TLS-required parameters and RDS-managed administrator password.
- RDS deletion protection, final snapshot required and seven days of backups.
- IMDSv2-required workers, immutable ECR tags and force deletion disabled.
- Five empty service-secret containers, seven-day recovery windows and no secret-version resources.
- Pod Identity agent `v1.4.0-eksbuild.4` and zones matching the readiness check.
- Mock checkout still explicitly enabled in the Helm runtime configuration.

Local checks pass no permission to deploy: they review configuration and available limits. A future apply may reveal additional service dependencies or changed conditions; capture the exact error rather than expanding access blindly.

## 4. Decisions before deployment approval

**Now recorded:** USD 75 allowance; target start **18 October 2026, 6:00 PM**; cleanup start **25 October 2026, 6:00 PM**, Asia/Colombo; protected state retained; final snapshot/release images retained for 14 days after actual teardown; application secrets use seven-day deletion recovery. See [the confirmed spending/retention guide](10-spending-cleanup-retention.md). These are planning decisions, not deployment or unattended-deletion approval.

Your intended retention is **one week**. The current core estimate remains **USD 51.15 for 168 hours**, plus variable charges and later platform components. See [cost details](10-foundation-cost-review.md). It is not an actual bill or spending cap.

Before the separate billable apply, record:

1. A spending allowance with headroom for traffic, logs, provisioning/deletion time, storage growth and later services.
2. Actual start and end-of-week cleanup date/time in **Asia/Colombo**. The week has not started because the foundation is not deployed.
3. Snapshot, ECR image, service-secret and Terraform-state retention choices. Retained artifacts can continue charging.
4. Approval for the fresh plan artifact and its billable configuration.

No AWS Budget, deployment, automatic shutdown or scheduled cleanup task has been created. The selected dates are recorded manual targets. Do not run `terraform apply` from this guide. If the source, operator network, account usage or deployment window changes, refresh the checks and plan before approval. After separate approval, deploy through the non-root profile and follow [10B–10E](10-cloud-deployment.md) to build DB roles/migrations, images/workload IAM, routing/frontend and hosted analytics; the foundation alone is not the full hosted application.

## References

- [AWS VPC quota definitions](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html), including NAT usage counted during creation/deletion.
- [EC2 quota guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-resource-limits.html).
- [EKS managed-node update behavior](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-update-behavior.html).
- Applied account values and version/orderability results are recorded in the linked live-readiness evidence, rather than inferred from documentation defaults.
