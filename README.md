# Wonderland — Python microservices + Angular

A step-by-step SE6020 theme park assignment implementation. **Current milestone: Step 10E private cloud Metabase and the hosted mock guest analytics flow are deployed and verified.** Cloud EKS runs eight API replicas, seven workers and one private Metabase replica on the existing nodes. The hosted frontend is https://main.d3vt08cs3xnlse.amplifyapp.com. Three dashboards and eight saved questions survived Metabase Pod replacement; check-in, duplicate handling, ride usage, event delivery and aggregate reporting passed. Checkout stays mock. Provider payments, backup restore and final assignment verification remain later work.

## Start here

Continue with [Step 10: staged Terraform and Helm deployment](docs/steps/10-cloud-deployment.md). Foundation, [private database bootstrap](docs/steps/10B-private-database.md) and [services/workers](docs/steps/10C-services-and-workers.md) are complete. Follow the [Step 10D execution and testing guide](docs/steps/10D-routing-and-frontend.md) for the deployed 57-resource routing layer, permissions, hosted checks and cleanup order. Track remaining assessed features in the [full assignment checklist](docs/ASSIGNMENT_COMPLETION.md).

For private cloud dashboards, follow [Step 10E: hosted mock analytics](docs/steps/10E-hosted-mock-analytics.md). Run `./scripts/open-cloud-metabase.ps1`, keep the tunnel open, then visit http://127.0.0.1:3001/collection/5-wonderland-cloud-mock. Port 3000 is the older local instance. Combined planning model: USD 64.41 before exclusions within the USD 75 allowance; cleanup remains 25 October 2026 at 6 PM Asia/Colombo. This is not a final bill or enforced spending cap.

Continue with [Step 09: AWS readiness and MOCK EKS/API Gateway feasibility](docs/steps/09-cloud-feasibility.md). It includes temporary SSO setup, account/quota checks, infrastructure, cost review, a Python probe, deployment/test commands and targeted cleanup. See [preparation evidence](docs/evidence/step09-validation.md) for the successful cloud test and verified cleanup.

Continue with [Step 08: mock Analytics and Metabase](docs/steps/08-mock-analytics.md). It includes connected guest-arrival, ride-popularity and hourly dashboards, worker heartbeat/backlog, restricted reporting access, saved SQL and the full walkthrough. See [Step 08 evidence](docs/evidence/step08-validation.md).

Continue with [Step 07: mock admission and ride usage](docs/steps/07-mock-admission.md). It covers protected staff check-in, per-guest duplicate safety, ride recording, simulation times, retries and owner visit history. See [Step 07 evidence](docs/evidence/step07-validation.md).

Continue with [Step 06: mock payment and demonstration tickets](docs/steps/06-mock-payment.md). It includes startup, success/failure tests, safe retries, expiry, the Python transaction and Angular screens. No real charges or admission credentials are issued. See [Step 06 evidence](docs/evidence/step06-validation.md).

Continue with [Step 05: outbox and AWS SNS/SQS](docs/steps/05-events-sns-sqs.md). It covers temporary non-root authentication, scoped workers, pricing projection rollout, retries, DLQs, verification and teardown. See [Step 05 evidence](docs/evidence/step05-validation.md) for what was verified and what remains pending.

Continue with [Step 04: booking, slots and history](docs/steps/04-booking.md), including the complete startup, code walkthrough, API examples and practice checklist. See [Step 04 validation](docs/evidence/step04-validation.md) for local evidence.

Read [Step 01: setup and first working slice](docs/steps/01-foundation.md), [Step 02: Cognito signup, login and roles](docs/steps/02-cognito-auth.md), then [Step 03: administrator attractions and pricing](docs/steps/03-admin-catalog.md). Keep [the roadmap](docs/ROADMAP.md) and [assignment checklist](docs/REQUIREMENTS.md) beside you. The earlier [full design guide](WONDERLAND_PYTHON_DEVELOPMENT_GUIDE.md) has been updated for Angular.

## Run locally on Windows

Prerequisites: Python 3.12, Node.js 22.19 (or an Angular-21-compatible supported version), Git, Docker Desktop's Linux engine. Commands below run from this repository directory in PowerShell. Scripts do not change machine-wide execution policy.

First-time setup (or refresh):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Start the APIs, mock Analytics worker and Metabase:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-analytics.ps1
```

Start Angular in a terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Open [Angular](http://127.0.0.1:4200), [API documentation](http://127.0.0.1:8001/docs), or [catalog JSON](http://127.0.0.1:8001/api/v1/attractions). The UI loads real database-backed data; no fallback mock catalog is used.

| Component | Local address |
|---|---|
| Angular | `http://127.0.0.1:4200` |
| Catalog FastAPI | `http://127.0.0.1:8001` |
| Booking FastAPI | `http://127.0.0.1:8002` |
| MOCK Payment FastAPI | `http://127.0.0.1:8003` |
| MOCK Admission FastAPI | `http://127.0.0.1:8004` |
| Metabase (separate local login) | `http://127.0.0.1:3000` |
| Mock staff check-in / visit history | Angular `/admin/admission` / `/visits` |
| Booking form / history | Angular `/book` / `/bookings` |
| Admin visit slots | Angular `/admin/slots` |
| PostgreSQL | `127.0.0.1:55432` |
| Development database | `wonderland`, isolated Catalog/Booking/Payment/Admission/Analytics schemas and aggregate reporting views |
| Metabase settings database | `wonderland_metabase`, separate application owner |
| Integration test database | `wonderland_test`, separate service schemas/roles |

Angular proxies admission requests to 8004, payment requests to 8003, booking/slot/policy requests to 8002 and remaining `/api/**` requests to Catalog on 8001. Restart Angular after proxy changes. Cloud deployment will replace this with gateway configuration. Compose binds ports to loopback; its checked-in credentials and enabled mock modes are for local development only.

## What works

- Four seeded attractions with category, thrill, age/height guidance, and details.
- Active-attraction browsing, detail API, and Angular category filtering.
- Four database-backed package tiers/prices in integer USD cents.
- PostgreSQL constraints, Alembic migration, and repeatable seed without resetting edited prices.
- Health endpoints, readiness checking storage, explicit frontend failure/retry states.
- Separate test database, Python integration tests, Angular interaction tests, production build, and GitHub check workflow.
- A Catalog Dockerfile and Compose migration/seed/API lifecycle.

Signup, email verification/resend, login, password recovery, signout, guarded account/admin pages and backend access-token verification are implemented. Follow Step 02 for identity setup. Step 03 adds protected attraction creation, edits, retirement, search/filtering, package price publication, preserved price history, stale-edit protection and atomic audit records. The four package definitions stay fixed. Step 04 adds dates/slots, guest limits, transactional capacity, price snapshots, duplicate-safe reservations, owner history/details, unpaid cancellation/expiry and atomic outbox storage. Step 06 adds local mock checkout, confirmation/failure, safe retries and printable per-guest demonstration tickets. Real provider payments remain future work.

## Verify

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

The test database name must end with `_test`; tests never reset development data. Start PostgreSQL first. Stop host API servers (Ctrl+C) before starting containers on the same ports:

```powershell
docker compose up -d --build catalog booking booking-maintenance payment admission
```

Compose runs migrations and repeatable seeds before starting the APIs. Run Angular separately as above. Source changes to containers require a rebuild. For Python hot reload, see Step 04's host development instructions using `start-backend.ps1` and `start-booking.ps1` with the expiry worker kept running.

## Stop

Use Ctrl+C in each host development server terminal, then:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

This preserves the database volume. Avoid `docker compose down -v` unless you deliberately want to erase all local database data. PostgreSQL initialization SQL runs only on a new volume; future changes to initialized databases need migrations or explicit bootstrap steps.

## Repository

```text
frontend/                 Angular standalone app, typed API client, features and tests
services/catalog/         Implemented FastAPI app, schema migration, seed, Dockerfile, tests
services/booking/         FastAPI bookings, slots, capacity, outbox, expiry, tests and Dockerfile
services/payment/         Local mock checkout API, isolated schema, tests and Dockerfile
services/admission/       Mock guest entry, ride usage, owner history, local outbox and tests
services/analytics/       Booking lifecycle consumer, local mock fact ingestion and reporting views
packages/common/          Shared event envelope, outbox publisher and inbox consumer utilities
deploy/local/postgres/    Local service role/schema and separate test DB initialization
deploy/helm/              Planned Kubernetes chart
infra/auth/               Deployed Cognito CloudFormation template
infra/                    Remaining cloud infrastructure planned
analytics/                Saved Metabase SQL and dashboard definitions
scripts/                  Windows setup, startup, verification, stop
docs/                     Learning steps, decisions, complete assignment checklist
.github/workflows/        CI checks (runs after publishing to GitHub)
```

Dependencies are locked in `frontend/package-lock.json` and the Python requirements files. Use `npm@11.6.2` for clean frontend installs: the preinstalled npm 10 resolver crashed during initial dependency resolution. No global Node/npm upgrade is required.

Publishing/connecting a GitHub remote and running Actions in GitHub are separate future actions. Local check execution does not prove a hosted workflow has run.

