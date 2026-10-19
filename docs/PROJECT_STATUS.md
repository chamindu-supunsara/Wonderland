# Wonderland: assignment review

Reviewed against the four-page SE6020 Cloud Computing brief on 19 October 2026.
This records the current implementation, not a claim that the whole assignment is finished.
The final release requested here is the mock demonstration version. The unfinished Stripe
integration has been removed. No real payments are collected.

## Done

| Assignment requirement | Implementation and evidence |
|---|---|
| Visitor and administrator accounts | AWS Cognito signup, email verification and login; administrator group; Python token verification; role and booking-ownership checks |
| Attraction browsing | Categories, descriptions, thrill/age/height guidance and active attractions in Angular |
| Attraction administration | Protected creation, editing and retirement; audit records and stale-edit protection |
| Booking | Individual/Couple/Family/Group package selection, 1–5 guests subject to tier limits, dates, time slots, capacity holds, cancellation/expiry and owner history |
| Editable prices | Prices stored in PostgreSQL, protected price publication/history and immutable booking price snapshots |
| Demonstration checkout and tickets | Mock success/failure, idempotent confirmation, capacity changes and printable per-guest references. This does not satisfy provider payment integration |
| Check-in and ride recording | Protected simulated staff check-in, duplicate prevention, timestamped ride usage and visitor history |
| Events and persistence | Service-owned PostgreSQL schemas, transactional outboxes, SNS/SQS, retries, dead-letter queues and consumer deduplication |
| Connected analytics | Private cloud Metabase: three dashboards/eight questions for arrivals, purchases/revenue by tier, popular rides, hourly activity and pipeline health. Facts and revenue are explicitly simulated |
| Containers and cloud hosting | Five Python service images; EKS workloads reached through API Gateway; Angular on Amplify; private RDS and private Metabase |
| Infrastructure source | Terraform roots for state/foundation/workloads/routing/analytics; Cognito and supporting CloudFormation; Helm workloads; scoped bootstrap and cleanup scripts |
| GitHub integration | Real repository, hosted CI, OIDC image publication, verified artifacts and operator-controlled deployment. Deployment/rollback rehearsal is documented in [Step 11](steps/11-deployment-evidence.md) |

## Pending or partial

| Requirement | What remains |
|---|---|
| Secure payment integration | **Not implemented in this final mock release.** The brief explicitly requires it on pages 2–3. Stripe was removed at the project owner's request; mock checkout is not equivalent. Obtain lecturer acceptance of that scope or implement a provider later |
| Available ticket tiers | Prices are editable; tier definitions and availability are still fixed. Protected tier metadata/availability management remains required |
| Password recovery | The Cognito recovery screen exists, but the real recovery walkthrough still needs evidence |
| Production payment/ticket/attendance evidence | Current tickets, arrivals, purchases and revenue demonstrate simulated workflows. Do not present them as real financial or gate transactions |
| Measured scalability and resilience | Complete concurrent booking/check-in tests, workload/queue bursts, service failure/degradation, retry/DLQ recovery and scaling measurements. Replicas alone are not proof |
| Complete communication encryption | Public endpoints and database connections use TLS. Private API Gateway/ALB/service hops remain HTTP; document or address that limitation |
| Database recovery | Perform a restore rehearsal and record recovery results. A Metabase Pod restart is not a database restore |
| Whole-stack reproducibility | Rehearse the complete clean deployment, including identity, secrets, migrations, seed data, workers, hosting and BI; document required owner actions |
| Cost evidence and cleanup | Record final delayed billing and execute the approved teardown/retention plan. The USD 75 allowance is a planning limit, not an AWS-enforced cap |
| Report and viva | Prepare the assessed report, architecture diagrams, design-pattern rationale, validation results, source/artifact links and full demonstration. Keep accurate source/assistance acknowledgements |

## Marking categories

| Component | Marks | Current assessment |
|---|---:|---|
| Solution report | 15 | Pending final report and diagrams |
| Microservices | 20 | Implemented for mock scope; payment and tier-management gaps remain |
| Kubernetes with API Gateway | 20 | Deployed and connectivity verified; measured failure/scaling evidence pending |
| Web interface, Amplify and Cognito | 15 | Deployed; mock payment limitation and recovery walkthrough remain |
| Monitoring and visualization | 10 | Connected cloud dashboards with simulated data; final demonstration/report evidence needed |
| Infrastructure as Code | 10 | Versioned infrastructure and deployment scripts; full clean-deployment rehearsal pending |
| Integration demonstration | 10 | GitHub and hosted mock workflows verified; final viva rehearsal pending |

These are coverage statements, not predicted marks.

## Deployment and cost boundaries

- Frontend: <https://main.d3vt08cs3xnlse.amplifyapp.com>
- Source: <https://github.com/chamindu-supunsara/Wonderland>
- Mock checkout, admission and analytics stay enabled; no provider credentials are needed.
- Reuse the existing cluster, database, gateway and hosting. No infrastructure expansion is part of this final application release.
- Existing planning estimate: USD 65.41 before usage/taxes/other exclusions, against a USD 75 allowance.
- Planned cleanup: **25 October 2026 at 6 PM Asia/Colombo**. Recovery-artifact review: **8 November at 6 PM**.
- Preserve Terraform state and the agreed recovery artifacts. Cleanup is not automatic.

The printed brief lists submission on 11 October and viva on 8 November 2026.
Any revised deadline or acceptance of mock payments must come from the lecturer.

## Repository cleanup

Removed the unfinished Stripe checkout, callback, reconciliation and recovery UI slice, its
setup scripts, tests and proposed migrations. Simplified the top-level guide and removed
duplicate outdated planning documents. Existing mock implementation, tests, deployment
safeguards and historical step guides are retained. Private rollback copies and raw execution
evidence remain outside the published source.

The sandbox migrations had already run locally. Their unused local tables are retained to
avoid deleting data; migration version markers are aligned with the restored mock source.
They were never applied to the cloud database. This cleanup does not change authorship or
remove the need to acknowledge adapted material or assistance in the report.
