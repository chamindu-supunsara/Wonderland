# Assignment completion tracker

The supplied four-page SE6020 brief defines the assessed requirements. This is our implementation checklist, not additional instructions from the document. Angular and the staged AWS architecture are our implementation choices. A row is complete only when implementation and verification evidence exist.

## Work in order

| Stage | Current state | Next exit condition |
|---|---|---|
| Steps 01-08 | Local Catalog/Booking/mock Payment/mock Admission/Analytics and Angular/Metabase implemented; Cognito real; bounded SNS/SQS checks completed | Keep existing evidence; do not call mock payment a provider integration |
| Step 09 | Complete; cloud mock connectivity and cleanup verified | Retain evidence and delayed billing check |
| Step 10A | Complete: approved 56-resource foundation deployed; 23 live checks passed; two Ready workers/eight healthy system pods; encrypted/versioned state; post-apply plan has no changes | Continue 10C–10E after completed 10B; keep USD 75 allowance and 25 October 6 PM cleanup target |
| Step 10B | Complete: private RDS, five isolated runtime roles/secrets, TLS 1.3, five migration heads and inventory seed verified; temporary privileged access removed; eleven cleanup checks passed | See [execution and recovery guide](steps/10B-private-database.md); restore rehearsal and hosted Metabase credentials remain later work |
| Step 10C | Complete: 45 event/IAM resources, five image digests, eight API replicas/seven workers, six worker identities, 34 final checks and verified pricing projection/duplicate handling; Terraform clean | Continue 10D; authenticated Booking/Admission event flows and poison-message redrive still need later evidence |
| Step 10D | Complete: 57 routing resources, Angular on Amplify, 23 public checks and 22 live checks, clean Terraform; real administrator/visitor signup, role denial, cross-owner denial, mock checkout/tickets/history passed | Continue 10E hosted BI and admission-to-dashboard walkthrough; see [execution guide](steps/10D-routing-and-frontend.md). Private backend hops remain HTTP |
| Step 10E | Complete for mock scope: private Metabase, three dashboards/eight questions, durable PostgreSQL metadata and verified hosted check-in/ride/event/analytics flow; temporary access removed | See [10E guide](steps/10E-hosted-mock-analytics.md) and [completion receipt](evidence/step10e-completion.json). Pod restart passed; backup restore, provider integration and later reliability work remain |
| Step 11 | Complete for controlled mock delivery: owned repository, 212 hosted Python tests, Angular/Terraform checks, exact OIDC trust, five image digests, verified artifact, deployment/rollback/final re-deployment (23 checks each), data preserved | See [Step 11 guide](steps/11-deployment-automation.md) and [execution summary](steps/11-deployment-evidence.md). Delivery uses explicit local SSO promotion; provider integration, database restore and measured resilience remain Step 12 |
| Step 12A - remaining required features | Pending | Provider sandbox, verified callbacks/reconciliation and corresponding purchase/revenue evidence, available-tier management, password recovery evidence |
| Step 12B - non-functional verification | Pending | Concurrent capacity/check-in tests, service outage/recovery, queue retry/DLQ, scaling behavior, security checks and measured cost |
| Step 12C - submission and viva | Pending | Report/diagrams/source links, assistance/source acknowledgement, clean deployment rehearsal and demonstrable final flow |

## Required feature gaps that must not disappear during deployment

- **Payment:** secure provider sandbox checkout, verified provider callbacks, idempotent state changes, reconciliation and operational handling of a paid booking that cannot confirm. No live customer charges are needed for a sandbox demonstration.
- **Tickets:** the brief permits a booking reference **or** QR code. We already have per-guest mock references; QR is optional, and trusted provider-backed ticket eligibility still needs verification.
- **Tier management:** pricing is editable, but package metadata is currently fixed. Finish protected management of available tiers without changing historical booking snapshots.
- **Purchases/revenue:** capture confirmed purchase timestamps and revenue by tier; deduplicate facts and separate mock from provider-sandbox transactions. Local arrivals/ride dashboards do not complete this requirement.
- **Arrival/ride activity:** manual authenticated staff recording can demonstrate simulated gate and ride input; physical hardware is not required by the brief. Preserve timestamps, ticket checks and duplicate safety.
- **Managed authentication:** complete the password recovery walkthrough and hosted visitor/admin/ownership denial checks.
- **Resilience:** remove/limit synchronous dependencies where needed, test degraded behavior and document remaining shared RDS/NAT failure modes. Two replicas without a measured outage test are not evidence of high availability.
- **Full infrastructure:** include the existing Cognito source, all Terraform roots, Helm/controller configuration, secrets/bootstrap/migrations, messaging and hosting in the clean deployment runbook. Do not claim the starter foundation deploys everything.
- **Monitoring:** actual/simulated data must be stored, timestamped and connected to the visualization tool; include purchases by tier, revenue, arrivals, popular rides and hourly activity.

## Evidence required for the final walkthrough

1. Repository URL, commit/release identifiers, passing checks and images by digest.
2. Reproducible cloud plan/apply and Helm rollout, with duration and resource ownership.
3. Hosted signup/login, attraction browsing, tier/date/slot selection and capacity enforcement.
4. Provider sandbox payment, verified confirmation, ticket reference, booking and visit history.
5. Administrator attraction creation/edit/retirement and tier/pricing changes.
6. Simulated guest check-in and ride usage reaching the connected dashboards.
7. Purchase counts/revenue by tier and peak/quiet activity queries with correct timezones.
8. Cross-user and visitor/admin denial tests, secrets/TLS checks and retry/failure demonstrations.
9. Scaling/load measurements, shared-failure limitations, costs and cleanup/retention results.
10. Report diagrams, decisions, citations and the viva rehearsal checklist.

The printed brief lists submission 11 October 2026 and viva 8 November 2026. Any revised arrangements must come from the lecturer; this tracker does not invent a new deadline or treat a cloud deployment as the complete submission.
