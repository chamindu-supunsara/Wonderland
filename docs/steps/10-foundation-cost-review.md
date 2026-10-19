# Step 10 foundation cost and retention review

Status: **foundation deployed and verified under explicit billable approval**. Terraform added 56 resources, changed/destroyed none; 23 live checks passed and the fresh plan reports no changes. Apply started **18 October, 1:52:45 PM**, keeping cleanup at **25 October, 6 PM**, Asia/Colombo. The core estimate is **USD 52.41** through cleanup start, before exclusions; the allowance remains **USD 75**. [Deployment evidence](10-foundation-deployment.md).

Rates were checked on 18 October 2026 using the AWS Price List GetProducts API with Mumbai filters. EKS standard-support and public IPv4 rates were checked against official AWS pricing pages. The model uses a 730-hour month for comparison, not an actual October invoice. It assumes two t3.medium workers, one db.t4g.small Single-AZ instance, one NAT gateway, 40 GB worker gp3, 20 GB RDS gp3 and six secrets including the RDS-managed master secret.

| Component | Quantity | Unit rate (USD) | 730-hour month model (USD) |
|---|---:|---|---:|
| EKS standard-support cluster | 1 | 0.1000 / hour | 73.00 |
| t3.medium Linux workers | 2 | 0.0448 / hour | 65.41 |
| NAT gateway | 1 | 0.0560 / hour | 40.88 |
| RDS db.t4g.small Single-AZ | 1 | 0.0420 / hour | 30.66 |
| NAT public IPv4 | 1 | 0.0050 / hour | 3.65 |
| Worker gp3 disks (GB) | 40 | 0.0912 / month | 3.65 |
| RDS gp3 storage (GB) | 20 | 0.1310 / month | 2.62 |
| Service secrets plus RDS master | 6 | 0.4000 / month | 2.40 |

**Core model: USD 0.3045/hour, or USD 222.27 for 730 hours.** This includes the listed storage/secret amounts prorated into an hourly equivalent. It is not a cost cap, complete platform quote or measured AWS bill. Credits, discounts and remaining Free Tier balances are not assumed.

You selected **one week** for the later foundation run. At 168 hours the same core model is **USD 51.15**, plus the exclusions below. This uses unrounded component rates rather than multiplying the rounded hourly equivalent. There is no automatic deletion schedule or spending cap. Record actual start/cleanup times when deployment is approved. The [permission and cost walkthrough](10-foundation-permissions.md) contains the weekly estimate, reviewed access scopes and owner-session preparation steps.

You have now selected a **USD 75 planning allowance**, target start **18 October 2026 at 6:00 PM** and cleanup start **25 October 2026 at 6:00 PM**, Asia/Colombo. Retain state, keep the final snapshot and release images for 14 days after actual teardown, and use seven-day recovery for application-secret deletion. [Confirmed choices and staged-cleanup implications](10-spending-cleanup-retention.md). This does not create a budget alert, hard cap, cleanup task or deployment approval.

The future internal ALB alone adds USD 0.0239/hour (about USD 17.45/730 hours), before its usage/LCUs. It is not in the current foundation root.

## Excluded costs

- NAT data processing (0.056 USD/GB), data transfer and cross-AZ traffic
- T3/RDS CPU credits
- CloudWatch ingestion/storage, ECR/image scans, S3 storage/versions/requests
- API Gateway, Amplify hosting/builds, ALB usage/LCUs and other later platform additions
- Additional backup/snapshot storage, RDS autoscaled storage above initial 20 GB
- Taxes, support, minimum billing increments, existing account resources

RDS can autoscale from the initial 20 GB up to 40 GB; that increases storage cost. Creating/deleting managed resources takes time that can be billable. Services have their own minimums and prorating rules. Keeping the foundation for a month costs much more than a short walkthrough. S3 state storage/version/request charges remain separately even when foundation compute is absent.

## Decide before applying

1. Whether this is a short rehearsal or a retained environment, and the expected deletion time.
2. A spending allowance with headroom for provisioning/deletion, data, logs and tests. A budget alert is not a hard shutdown or spending cap.
3. Whether Single-AZ RDS and one NAT are acceptable demo tradeoffs. They remain shared failure points; production alternatives need a new quote.
4. How to retain RDS snapshots, secrets, ECR images and state while cleaning up. Deletion protection is enabled; final snapshots are required; ECR force deletion is disabled. Retained artifacts can incur costs.
5. Exact foundation deployment permissions. The reviewed addition has now been owner-provisioned and CLI-verified; existing grants remain. This validates policy presence and an EC2 dry-run authorization, not every downstream runtime call. Review any future policy changes separately.
6. Fresh account quotas/usage and orderable versions. On 18 October, 17 checked quota comparisons and four availability checks passed; Standard On-Demand is now 16 vCPUs with zero used and four planned. The regenerated plan still has 56 additions, no changes/deletions. See [pre-deployment checks](10-pre-deployment-checks.md). Refresh if conditions change; checks are not capacity reservations or proof of every runtime creation permission.

No automatic deployment, budget creation or teardown has been scheduled. The old Step 09 billable test approval does not cover this foundation.

## Sources and evidence

- [AWS EKS pricing](https://aws.amazon.com/eks/pricing/): standard-support cluster hourly rate.
- [AWS VPC pricing](https://aws.amazon.com/vpc/pricing/): public IPv4 and networking charges.
- [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/): secrets and API calls.
- [Reviewed rate data and SKUs](../evidence/step10-foundation-costs.json): exact regional Price List results and model inputs.
- [Unapplied foundation plan summary](../evidence/step10-foundation-plan.json).
- [Deployment guide](10-cloud-deployment.md).
