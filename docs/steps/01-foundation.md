# Step 01 — Run and understand the first working slice

Goal: show PostgreSQL-backed attractions and ticket packages in Angular through a Python API. This step is complete when you can start the services, trace a browser request, explain the tables, filter rides, inspect package prices, and run the checks. Login/booking/payment/admin writes are later milestones.

## 1. Understand the pieces

```text
Browser at :4200
  -> Angular component
  -> typed CatalogApi HTTP client
  -> Angular dev proxy for /api/**
  -> FastAPI at :8001
  -> SQLAlchemy session
  -> PostgreSQL at :55432, wonderland.catalog tables
```

Angular uses TypeScript and standalone components with signals; FastAPI uses Python. PostgreSQL runs in Docker. The Python service can run directly in a project virtual environment for quick reloads or in its Docker image. There is no production cloud deployment yet.

## 2. Check tools

Open PowerShell and enter:

```powershell
Set-Location D:\Courses\Microservices
python --version
node --version
npm.cmd --version
docker version
```

Python 3.12 and Node 22.19 were present during setup. Angular 21 supports this Node version. Start Docker Desktop and wait for its Linux engine if `docker version` only shows a client or a named-pipe error. The project uses local Angular CLI dependencies, so you do not need a global `ng` installation.

## 3. First setup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The script checks Docker, creates `.venv` if missing, installs locked Python dependencies, copies the example environment file only when missing, starts PostgreSQL, applies Alembic migrations, adds missing demo records, and installs locked Angular dependencies. Existing edited prices are preserved by the seed. Do not run seeds simultaneously from multiple terminals.

Read `services/catalog/.env.example`. The real `.env` is ignored by Git. Local credentials are deliberately development-only. Port **55432** avoids the database port Windows blocked on this machine. Cloud credentials will come from managed secrets later.

The SQL in `deploy/local/postgres` creates a restricted Catalog role/schema and a separate test role/database. Initialization scripts run on a fresh volume only. Subsequent table changes belong in Alembic migrations.

## 4. Start Python in terminal A

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

Open `http://127.0.0.1:8001/docs`. Try:

- `GET /health/live` — the process responds.
- `GET /health/ready` — required catalog storage is accessible.
- `GET /api/v1/attractions` — active rides, sorted by name.
- `GET /api/v1/attractions?category=WATER` — server-side category filtering.
- `GET /api/v1/attractions/{id}` — one active attraction; retired/missing IDs return 404.
- `GET /api/v1/ticket-tiers` — active tiers joined to their active prices.

Useful files in reading order: `app/config.py`, `app/db.py`, `app/models.py`, `app/schemas.py`, `app/api/routes.py`, `app/main.py`, then `app/seed.py`. `alembic/versions/0001_catalog.py` is the versioned database creation step. The API never calls `create_all()` at startup.

## 5. Start Angular in terminal B

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Open `http://127.0.0.1:4200`. You should see four seeded experiences. Try the category filters and expand "Before you ride". Open "Tickets & tiers": Individual $40, Couple $75, Family $140, Group $165, all USD package totals.

There is no active checkout button until booking/payment are implemented. "Coming soon" describes that stage honestly.

Read Angular files in this order:

1. `src/main.ts` bootstraps the application.
2. `src/app/app.config.ts` provides routing and HttpClient.
3. `src/app/app.routes.ts` lazily loads the two feature pages.
4. `core/api/catalog.models.ts` describes the response shapes.
5. `core/api/catalog-api.ts` makes HTTP calls with a timeout.
6. `features/attractions/attractions-page.ts` stores loading/error/data/filter state in signals.
7. Its HTML renders cards and a category filter; SCSS styles the page responsively.
8. The tickets feature renders integer cents as dollars using Angular's CurrencyPipe.

`proxy.conf.json` routes local API requests. The API base URL has an injection token so cloud configuration can point at API Gateway later. No Python URL is hard-coded in individual components.

## 6. Inspect real data without changing it

```powershell
docker compose exec postgres psql -U catalog_dev -d wonderland -c "SELECT name, category, status FROM catalog.attractions ORDER BY name;"
docker compose exec postgres psql -U catalog_dev -d wonderland -c "SELECT code, min_guests, max_guests FROM catalog.ticket_tiers ORDER BY max_guests;"
```

Why separate prices? A tier defines the allowed party size; a price version defines a package amount. The database prevents invalid guest ranges, nonpositive prices, duplicate tier/version pairs, and two simultaneously active prices for one tier. Later admin updates will replace the active price transactionally and publish events. Booking will copy the accepted price rather than consulting the latest price for historical purchases.

## 7. Trace the integration

In browser Developer Tools, use Network, reload, and find `/api/v1/attractions`. Inspect its JSON response. Find the corresponding FastAPI route and database query. This is a useful viva explanation of frontend/backend/database integration.

Stop the backend briefly: Angular should show an error and a retry button, not sample ride data. Restart it and retry. This proves failure handling at the first boundary; it does not yet prove the assignment's complete microservice fault-tolerance requirement.

## 8. Run verification

From the root, with PostgreSQL running:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

This runs Python lint/format checks, integration tests against `wonderland_test`, Angular HTTP/component tests, and a production build. Tests use actual PostgreSQL constraints. Frontend unit tests mock HTTP deliberately and are separate from a live integration smoke check.

The Python tests check retired attraction visibility, suitability, missing/invalid IDs, active price selection, database pricing constraints, readiness failures, and repeatable seeds. Angular tests check API configuration, loading/filtering, recovery after a failed request, and cents-to-package-price rendering.

## 9. Try containerized Python

Stop the host Python API using Ctrl+C. Leave the frontend running, then:

```powershell
docker compose up -d --build catalog
docker compose ps -a
```

The one-shot migration and seed containers should exit successfully; the Catalog container should become healthy. Angular continues to call the same port. To return to host Python development, run `docker compose stop catalog`, then the backend startup script. Do not run both APIs on port 8001.

## 10. Save work in Git

The repository is initialized locally during this milestone. Check it with:

```powershell
git status
```

Review changes and make your first commit when ready. No remote repository is invented, no code is pushed, and no GitHub credentials are stored. Connecting your actual GitHub repository is a later explicit step. `.env`, `.venv`, `node_modules`, generated builds, and database state are excluded from Git.

## Troubleshooting

- **npm 10 reports `edgesOut`:** clean installs use `npx.cmd --yes npm@11.6.2 ci`; this does not replace global npm.
- **`npm.ps1` execution policy error:** scripts use `npm.cmd`, and the documented script launch changes policy only for that PowerShell process.
- **Docker pipe/engine error:** start Docker Desktop's Linux engine first.
- **Database connection refused:** `docker compose up -d postgres --wait`, then inspect `docker compose logs postgres`.
- **Port already in use:** stop the other host/container API rather than starting duplicate servers. If changing a port, update Compose, `.env`, tests, proxy, and documentation consistently.
- **Missing catalog tables:** run setup again, or apply `python -m alembic upgrade head` from `services/catalog` using the project interpreter.
- **An existing database volume lacks the test role/schema:** inspect its initialization history. Apply the missing bootstrap deliberately; do not erase a populated volume as a routine fix.
- **UI shows no data:** inspect backend readiness and Network responses; do not add hard-coded fallback data.
- **Database access denied inside Codex sandbox:** tool-level approval may be required for localhost access; this is separate from normal application credentials.

## What comes next

Managed identity and role checks, then protected administrator attraction/pricing changes. Booking follows with date/slot selection, capacity, idempotency, history, and event integration. Use `docs/PROJECT_STATUS.md` to ensure later work covers every assignment component.

