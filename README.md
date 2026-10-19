# Wonderland

A theme park booking application for the SE6020 Cloud Computing assignment.
Angular provides the visitor and administrator screens. Python/FastAPI services handle
the catalog, bookings, mock checkout, simulated admission and analytics.

**Demo:** https://main.d3vt08cs3xnlse.amplifyapp.com

**Repository:** https://github.com/chamindu-supunsara/Wonderland

Checkout is a simulation: no real money is collected. The unfinished Stripe integration
has been removed. See the [assignment review](docs/PROJECT_STATUS.md) for the done/pending
list and the payment requirement that remains unmet.

## Run locally

Use Python 3.12, Node.js 22.19, Docker Desktop's Linux engine and PowerShell.
Run these commands from the project directory:

```powershell
./scripts/setup.ps1
./scripts/start-analytics.ps1
```

In a second terminal:

```powershell
./scripts/start-frontend.ps1
```

Open Angular at http://127.0.0.1:4200 and local Metabase at http://127.0.0.1:3000.
Configure the existing Cognito pool/client with [the authentication guide](docs/steps/02-cognito-auth.md).
Local service ports are Catalog 8001, Booking 8002, Payment 8003 and Admission 8004.
PostgreSQL is bound to loopback on port 55432. Local Compose credentials are for development.

## Check the project

```powershell
./scripts/verify.ps1
```

This runs Python integration tests, Angular tests and a production frontend build.
Tests use a separate database ending in `_test`. To stop local containers while keeping
their data, run `./scripts/stop-local.ps1`.

## Project layout

| Folder | Purpose |
|---|---|
| `frontend/` | Angular visitor/admin screens and tests |
| `services/` | Five Python services, migrations, Dockerfiles and tests |
| `packages/common/` | Shared event delivery and deduplication utilities |
| `infra/` | Terraform, Cognito and supporting AWS templates |
| `deploy/` | Helm charts, database bootstrap and local configuration |
| `analytics/` | Dashboard definitions and reporting SQL |
| `scripts/` | Setup, checks, deployment and cleanup |
| `docs/steps/` | Implementation and operations walkthroughs |

## Cloud operation

The application uses the existing Mumbai EKS cluster, API Gateway, private RDS, SNS/SQS,
Amplify and private Metabase. Follow [the deployment guide](docs/steps/11-deployment-automation.md)
and [database/bootstrap guide](docs/steps/10B-private-database.md). Releases are checked in
GitHub, published by image digest and promoted using the operator's temporary AWS SSO session.

For cloud dashboards run `./scripts/open-cloud-metabase.ps1`, keep the tunnel open,
and visit http://127.0.0.1:3001. Metabase has its own administrator login.

The agreed trial allowance is USD 75; the planning estimate is USD 65.41 before exclusions.
Keep cleanup on **25 October 2026 at 6 PM Asia/Colombo** and recovery review on **8 November**.
See the [assignment review](docs/PROJECT_STATUS.md) for limitations and remaining work.
