# Wonderland Booking

Implemented FastAPI service on local port 8002. Owns the `booking` PostgreSQL schema and role; uses Catalog's public HTTP API for package quotes and independently validates Cognito access tokens.

See [the complete Step 04 guide](../../docs/steps/04-booking.md) for setup, configuration, architecture, API payloads, Angular walkthrough, concurrency/ownership tests and troubleshooting.

From the repository root: `docker compose up -d --build catalog booking booking-maintenance`. Compose bootstraps service roles/schemas, migrates, seeds future slots, then runs the API and prepayment expiry worker. Host hot reload is available through `scripts/start-booking.ps1` after setup.

Bookings are 30-minute unpaid holds with server-owned price snapshots. Owner cancellation and expiry release places transactionally. Step 05 adds SNS publishing, retry state, a pricing inbox and versioned price projection. Follow [Step 05](../../docs/steps/05-events-sns-sqs.md) for scoped workers and the explicit projection-mode rollout; HTTP pricing remains active until continuous workers are authenticated. Before adding a payment provider, replace direct unpaid expiry/cancellation with reconciliation for unresolved payment outcomes.

