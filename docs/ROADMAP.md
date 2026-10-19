# Build roadmap — Angular + Python

Build and understand one tested milestone at a time. Check off work only when the implementation and evidence exist.

| Step | Scope | Exit condition | Status |
|---|---|---|---|
| 01 | Repo, Angular, FastAPI Catalog, PostgreSQL, migrations, seeds, checks | UI displays real attractions and package prices | Implemented; see validation record |
| 02 | Managed identity and authorization | Cognito signup/login, visitor/admin roles, backend JWT validation, ownership foundation | Implemented and deployed; real visitor/admin login, denial and reload verified; real password recovery check pending |
| 03 | Administrator Catalog | Protected attraction creation/edit/retirement and package pricing; price history and audit retained | Implemented and verified locally; package metadata fixed; slots in Step 04 |
| 04 | Booking service and Angular booking form | Dates/slots, tier validation, atomic capacity, idempotency, pending bookings, own booking history | Implemented and verified locally; unpaid cancellation/expiry and admin slots included |
| 05 | Event transport and transactional outbox | Durable SNS/SQS delivery, per-consumer queues, retries/DLQs, deduplication, pricing projection | Implemented; AWS stack and bounded delivery/duplicate/redrive checks passed; continuous scoped workers and projection rollout await non-root SSO |
| 06 | Mock checkout and demonstration tickets; provider integration later | Immutable mock decisions, retry-safe capacity confirmation, per-guest demo tickets; provider sandbox/callbacks/reconciliation still required | Local mock flow implemented and verified; see Step 06 guide/evidence |
| 07 | Mock Admission service and staff pages | Trusted independent ticket projection, duplicate-safe guest entries, ride events, own visit history | Implemented and verified locally; HTTP ticket projection and local mock outbox; Admission event transport/real gate integration remain future work |
| 08 | Mock Analytics + Metabase | Durable facts, connected arrival/ride/hourly dashboards, correct metrics and measured freshness | Implemented and verified locally; restricted reporting connection, persistent Metabase metadata, 6 saved questions / 2 dashboards; local delivery, no new AWS transport |
| 09 | Cloud platform experiment (bring forward early) | Account permissions verified; API Gateway reaches a minimal EKS workload | Complete: cloud mock test passed on 18 October; two Ready pods, five successful API Gateway responses, booking path 404; stack and all 18 resource categories verified removed |
| 10 | Complete Terraform + Helm deployment | EKS, gateway, RDS, identity, queues, secrets/TLS, Amplify Angular, reproducible setup | 10A complete: approved 56-resource foundation deployed; 23 live checks passed; two Ready workers; zero-change post-apply plan; 10B–10E pending |
| 11 | GitHub deployment integration | Real remote, hosted checks, OIDC/ECR/rollout/build workflow and release evidence | Planned |
| 12 | Finish assessed feature gaps, reliability, report and viva | Provider sandbox, purchase/revenue reporting, available tiers, recovery; measured concurrency/failures/scaling; report and clean redeployment demo | Planned; see assignment completion tracker |

The ordering is a learning sequence. Do the cloud feasibility experiment early enough to discover account restrictions; do not wait until all features are built. Events are developed before final paid booking integration. Admin/visitor write flows must use verified authentication, not a client-provided role.

Current lesson: [cloud readiness results and deployment access](steps/09-deployment-access.md), with [validation evidence](evidence/step09-validation.md). The mock app stays local. Admission-to-Analytics delivery works locally with commit-before-ack duplicate safety; see [Step 08 evidence](evidence/step08-validation.md). The approved cloud probe deployment and API Gateway connectivity test passed. Final cleanup is verified; no experiment runtime resources remain. Step 10A foundation preparation is underway; see [the Step 10 guide](steps/10-cloud-deployment.md) and [complete assignment tracker](ASSIGNMENT_COMPLETION.md). AWS transport for Admission, Step 05 continuous workers and pricing projection rollout still await separate worker-source setup. Provider payments and real attendance remain pending. A real password recovery walkthrough remains pending separately from Step 02.

