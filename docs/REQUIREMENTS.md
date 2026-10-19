# Assignment traceability checklist

See [the ordered full-assignment completion tracker](ASSIGNMENT_COMPLETION.md) and [Step 10 cloud deployment](steps/10-cloud-deployment.md). The assignment PDF is the authority for assessed requirements. This implementation uses Angular as the permitted similar frontend framework. Architecture/product policies are recommendations, not extra assignment instructions.

| Requirement | Current coverage | Remaining work / evidence |
|---|---|---|
| Visitor and administrator profiles | Cognito identity/roles, account page, owner booking and mock visit/ride history implemented; real role access verified | Hosted profile and role/ownership evidence later |
| Secure signup/login | Real signup, verification, visitor/admin login, denial and session reload verified; Python JWT/role tests; Booking owner filtering | Real password recovery check |
| Browse attractions with description/category/suitability | Implemented | Cloud deployment evidence later |
| One tier per booking, 1–5 guests overall | Implemented strict Booking validation and package-specific limits | Paid integration later |
| Individual/Couple/Family/Group pricing | Persisted, displayed, protected versioned admin changes and booking snapshots | Event-based pricing projection later |
| Visit date and preferred slot | Implemented park timezone/date policy, admin slots, availability and atomic capacity; concurrency tests pass | Cloud/load evidence later |
| Secure payment integration | Local MOCK checkout implemented; not provider integration | Hosted sandbox, verified callbacks, reconciliation and compensation |
| Digital ticket reference or QR | Owner-only per-guest MOCK references and printable demonstration tickets implemented | Trusted paid admission credentials; no QR implementation yet |
| Own booking and visit history | Owner-filtered bookings and MOCK per-guest visit/ride history with pagination implemented | Real admission data and cloud evidence later |
| Create/update/retire attractions | Protected Python API and Angular screens; real admin walkthrough verified | Cloud deployment evidence |
| Manage pricing and tiers | Four package definitions displayed; protected price publication/history and booking snapshots implemented | Required available-tier metadata management is unfinished; preserve historical snapshots when adding it |
| Actual gate arrivals | Administrator mock staff page, unique simulated check-in, local Analytics delivery and connected arrival reporting implemented | Real arrival/gate integration and AWS delivery later |
| Purchased tickets/revenue by tier | Planned | Trusted confirmed-purchase facts, reporting |
| Popular rides/activities | Durable MOCK ride facts, ranked connected Metabase chart and stable attraction grouping implemented | Real data and cloud delivery/deployment evidence |
| Peak and quiet times | Connected 24-hour Colombo arrival/ride chart with zero-filled hours over observed mock dates | Real attendance evidence; zero activity does not establish opening hours |
| Persisted timestamped monitoring events | Booking/Catalog bounded SNS/SQS delivery; atomic Admission mock events, local commit-before-ack Analytics facts, heartbeat/backlog and connected BI | Continuous non-root AWS workers and cloud Admission transport/deployment |
| Connected Power BI/Superset/Metabase | Local Metabase with separate persistent PostgreSQL app DB, aggregate-only reporting role, 2 dashboards / 6 saved questions | Hosted BI and real/financial data integration |
| Scalability | Foundation only | Replicas/HPA/nodes/queue buffering and measured load tests |
| Security | Validation, separate local schema roles, Cognito JWT/roles and Booking ownership | Production hardening, secrets, TLS, encryption at rest, cloud permissions |
| Fault tolerance | Durable outboxes, retry schedules, processing/delivery DLQs and consumer deduplication; AWS redrive tested | Production supervision/replicas, measured outages and scaling |
| Cost efficiency | Local development established | Current cloud estimate, right-sizing/autoscaling and teardown |
| Solution report and architecture diagrams — 15 marks | Design guide and roadmap | Assessed report and implementation evidence |
| Microservice implementation — 20 marks | Catalog, Booking, mock Payment, mock Admission, Analytics facts and reporting implemented locally | Provider integration, AWS Admission transport and hosted evidence |
| Kubernetes + API Gateway — 20 marks | Step 09 isolated MOCK probe deployed and verified through Gateway/VPC link/ALB/EKS; cleanup verified | Deploy the full application through Step 10 and capture hosted flows/failure evidence |
| Web interface + Amplify/Cognito — 15 marks | Angular browsing/auth/admin/booking/mock checkout/tickets/staff admission/own visit history implemented | Real payment/admission integration and Amplify Hosting |
| Monitoring/BI — 10 marks | Local durable mock outbox ingestion, reporting facts, connected Operations/Health dashboards, measured fresh delivery | AWS Admission transport and hosted evidence; revenue integration later |
| Infrastructure as Code — 10 marks | Cognito/messaging CloudFormation; Step 09 experiment proven; Step 10A state storage deployed/verified, Terraform roots and Helm starter locally validated, live foundation plan prepared but unapplied | Complete Step 10 cloud deployment and clean redeployment rehearsal |
| Integration demonstration — 10 marks | Local first slice | Real GitHub integration and complete hosted flow |
| Containerized services | Catalog, Booking, mock Payment and mock Admission Dockerfiles/Compose; migration/seed/expiry lifecycle | Cloud ECR, immutable tags and remaining worker deployment |
| Viva: run infrastructure stack and demonstrate | Planned | Deployment rehearsal, timing, recovery notes |
| Report to Moodle and artifact links | Planned | Report plus repository/deployment links |
| Individual work and assistance acknowledgement | Ongoing | Cite adapted work; follow institution rules and brief |

Policy decisions: initial Family/Group minimum guest counts are 1 because the brief says "up to"; package price stays fixed below maximum size. PostgreSQL money is integer USD cents. Attractions are retired rather than deleted. Physical gate/ride input is simulated through authenticated staff pages. One guest ticket per admitted person; re-entry is out of initial scope.

Printed dates: submission 11 October 2026, viva 8 November 2026. Confirm any changed submission arrangement with the lecturer.

