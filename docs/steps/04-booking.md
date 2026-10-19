# Step 04 — Booking service, dates, capacity and my bookings

This lesson is implemented in your project. Work through the numbered walkthrough first, then follow the code reading sequence to understand each layer. Keep Step 02's Cognito configuration and Step 03's Catalog running. No additional AWS resource is required for this local milestone.

## 1. Understand the result

A signed-in visitor selects one ticket package, a whole guest count, a park date and a time slot. Angular shows a review before submitting. Python verifies the Cognito access token, obtains the package price from Catalog, checks capacity inside a PostgreSQL transaction, and creates a 30-minute `PENDING_PAYMENT` reservation. The visitor can see only their own booking history and cancel unpaid holds.

Administrators can add non-overlapping time slots and see available/held guest places. An administrator can also reserve as a visitor; being an administrator does not grant access to another person's booking history.

Payment, confirmed purchases, QR tickets and admission are later milestones. The `WL-...` reference identifies a reservation; it does not establish payment or park entry.

```mermaid
sequenceDiagram
  participant UI as Angular :4200
  participant B as Booking :8002
  participant C as Catalog :8001
  participant DB as PostgreSQL / booking
  UI->>B: Access JWT + package, guests, slot, price version + retry key
  B->>B: Validate Cognito identity and input
  B->>DB: Begin transaction; lock owner + retry key
  B->>C: Read current public package quote
  C-->>B: Price, currency, version and guest limits
  B->>DB: Lock slot; expire old holds; check remaining places
  B->>DB: Insert pending booking + reserve capacity + insert outbox event
  DB-->>B: Commit all changes together
  B-->>UI: Reservation reference, stored price, expiry
  UI->>B: Load my bookings using verified account identity
```

## 2. Start the local application

Use PowerShell in `D:\Courses\Microservices`. Start Docker Desktop's Linux engine first.

For an existing installation with dependencies already installed:

```powershell
docker compose up -d --build catalog booking booking-maintenance
docker compose ps
```

Compose creates Booking's local roles/schema, applies its migration, seeds slots and starts the APIs. Expect Catalog on **8001**, Booking on **8002**, PostgreSQL on **55432**, and both APIs healthy. Migration/seed/bootstrap containers exit successfully after completing their work.

In a separate terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

If Angular was already running before this milestone, stop it with Ctrl+C and start it again. The new proxy routes are read at startup.

For a fresh checkout or missing dependencies, run the setup first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The setup installs locked Python/Angular dependencies, migrates both schemas and seeds data. It creates an ignored `services/booking/.env` from your existing Catalog configuration, replacing the default local database credentials with Booking's credentials. Existing `.env` files are preserved. If you customized the Catalog database URL, configure Booking's separate URL explicitly rather than reusing Catalog's database role.

Check Booking's `.env` locally contains these settings; never copy credentials or tokens into chat:

```dotenv
DATABASE_URL=postgresql+psycopg://booking_dev:booking_dev_only@localhost:55432/wonderland
CATALOG_URL=http://127.0.0.1:8001
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_aBuDlZ9RC
COGNITO_APP_CLIENT_ID=202ssal4mlube43ttm0j5m3k4i
```

These Cognito identifiers are public configuration. Keep using your established pool and public application client; no AWS access key is needed by this API. The database credentials shown are local development credentials only. Compose overrides the database and Catalog URLs with Docker network addresses.

For Python editing with automatic reload, stop only the API containers first, keep PostgreSQL running, and use separate terminals:

```powershell
docker compose stop catalog booking
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-booking.ps1
```

Keep `booking-maintenance` running in Docker, or run its host equivalent from `services/booking` in another terminal:

```powershell
..\..\.venv\Scripts\python.exe -m booking_app.maintenance
```

Use one API process per host port. Rebuild containers after Python edits when using Docker; they do not mount source code for hot reload.

## 3. Create or inspect visit slots as an administrator

1. Sign in using your existing administrator account.
2. Open `http://127.0.0.1:4200/admin/slots`, also linked from the main admin page.
3. Choose a future date, start/end times and guest capacity, then click **Add time slot**.
4. Read the confirmation and availability for that date.
5. Try the same or an overlapping window: Python must return a conflict. Adjacent windows, such as 09:00–12:00 and 12:00–15:00, are allowed.

Times are always **Asia/Colombo (UTC+05:30)**. The date policy permits today through 90 days ahead, inclusive, provided the start time is still in the future. Start/end must be whole local minutes on the same day, and end must be later. Capacity is a whole number from 1 to 10,000, measured in **people**, not bookings.

The repeatable seed supplies the next seven days starting tomorrow, with 09:00–12:00, 12:00–15:00 and 15:00–18:00 windows of 100 guest places. An empty date is valid: choose a seeded date or add a slot. Today may have no slots, especially when testing in the evening.

There is no slot edit/delete operation in this lesson. Bookings depend on these windows. Later changes require a deliberate rescheduling/capacity policy rather than changing an occupied slot silently.

To extend the rolling demonstration data later:

```powershell
docker compose run --rm booking-seed
```

Seeding skips overlapping windows and preserves existing capacity and reservations. It runs during setup/Compose lifecycle; there is no nightly seeding scheduler.

## 4. Make your first reservation

1. Open `http://127.0.0.1:4200/tickets` and select a package's booking link, or open `/book` directly.
2. Choose **one package**. Individual permits 1 person, Couple 2, Family 1–4 and Group 1–5. The price is per package, so Family with fewer than four people still costs the Family package price.
3. Enter a whole guest count within those limits.
4. Choose tomorrow or another date containing a future window.
5. Select a time slot. Slots with insufficient places are disabled.
6. Click **Review reservation →**. Check the package, guest count, price and local visit time.
7. Click **Reserve pending payment** once.
8. Expect a reservation reference and an unpaid hold expiry. Click **View reservation →**.

Prices come from your current Catalog data, including Step 03 administrator changes. Python reads the quote again when creating a new reservation. If the form's price version is stale, creation returns 409; reload prices, review the new price, and submit again. Browser-supplied amount, owner and status fields are rejected.

Changing the guest count or seeing an available slot does not reserve anything. Capacity is reserved only when the transaction commits. Another visitor may reserve the last places before your submit; Python then returns a clear conflict.

On a timeout/network failure, use **Retry same reservation**. Angular retains the exact body and UUID retry key while that page remains open. If the first request committed but its response was lost, the retry returns that same booking without reserving more places. Do not refresh/navigate away and immediately make a new reservation: the pending attempt is held in component memory, so check **My bookings** after navigation/reload before starting another attempt.

## 5. View history, details and cancellation

Open `http://127.0.0.1:4200/bookings`, also available from My account. History is newest first, 20 records per page, with Previous/Next controls. It shows stored package/price version, guests, visit date/time, reference, creation time and current status. A detail URL can be reloaded while signed in.

For a pending reservation, click **Cancel unpaid reservation**, inspect the inline confirmation, then **Confirm cancellation**. **Keep reservation** dismisses the confirmation. Cancellation releases capacity atomically and retains the historical record. Repeating cancellation cannot release the same places twice.

The prepayment maintenance worker expires holds every 15 seconds. Availability/history/detail reads also process due holds, so reads recover even if the worker was temporarily stopped. An expired hold changes to `EXPIRED`, releases its guest places once and remains in history. Use **Refresh booking status** to fetch current state; the page does not continuously poll or implement a live countdown.

| State | Meaning | Capacity effect |
|---|---|---|
| PENDING_PAYMENT | Unpaid reservation before expiry | Guest places held |
| CANCELLED | Owner cancelled the unpaid reservation | Held places released |
| EXPIRED | The unpaid hold reached its expiry | Held places released |

## 6. Understand the Python implementation, in order

Read these files under `services/booking`:

| File | What to learn |
|---|---|
| `booking_app/config.py` | Independent service settings, Catalog URL and Cognito configuration |
| `booking_app/db.py` | Own SQLAlchemy engine, sessions and declarative Base |
| `booking_app/models.py` | Slot counters, booking snapshots, ownership, idempotency and outbox |
| `alembic/versions/0001_booking.py` | Frozen initial table/index/constraint migration |
| `booking_app/schemas.py` | Strict request validation and explicit response fields |
| `booking_app/auth.py` | Cognito JWT verification and administrator dependency |
| `booking_app/catalog.py` | Bounded, time-limited public HTTP quote lookup |
| `booking_app/main.py` | API routes and transactional business rules |
| `booking_app/seed.py` | Repeatable future slot creation |
| `booking_app/maintenance.py` | Prepayment expiry loop |
| `tests/test_booking.py` | Integration and real competing-transaction tests |
| `tests/test_identity.py` | Signed JWT validation without bypassing verification |

Booking owns a `booking` PostgreSQL schema and independent migration version table. Catalog owns `catalog`. Roles separate access even though both local schemas share one database instance. Booking has no cross-schema foreign key and never queries Catalog tables. Package identifiers are external references; booking prices and names are retained as snapshots.

The capacity formula is:

```text
remaining = capacity_guests - held_guests - confirmed_guests
```

`confirmed_guests` is reserved for later payment work and stays zero in this milestone. For new reservations, the transaction acquires a PostgreSQL advisory lock for the authenticated owner/retry key. A unique `(user_sub, idempotency_key)` constraint backs that rule. Identical retries return 200; new bookings return 201; changed payload under the same key returns 409.

Then Python locks the selected slot with `SELECT ... FOR UPDATE`, expires its due holds, and checks the requested guest count. Competing requests wait for that same row lock, then see the committed counter. Database CHECK constraints additionally prevent negative counts or held plus confirmed above capacity. Cancellation and expiry take the same slot lock before updating bookings, keeping capacity transitions consistent across API/worker processes.

One database transaction stores the booking, capacity increment and `BookingPaymentRequested` outbox event. Failure rolls back all three. Cancellation and expiry similarly store `BookingCancelled`/`BookingExpired` with the counter change. The outbox currently stores events only: there is no SNS/SQS publisher, retry delivery or consumer yet.

Catalog quote lookup is an interim synchronous dependency. New reservations return 503 if pricing cannot be read; an already recorded identical retry can succeed without Catalog. Prices are correct for the quote read by Booking, but a Catalog publication after that read is not serialized with the Booking transaction. Step 05 will introduce versioned pricing projection/event transport; this lesson does not claim a distributed transaction across services.

## 7. Understand Angular, in order

| File under `frontend` | Responsibility |
|---|---|
| `src/app/core/api/booking-api.ts` | Typed requests/responses, UUID retry header, bounded client timeouts |
| `src/app/features/booking/booking-page.ts` and `.html` | Options, guest/date/slot validation, review, submission and safe retry |
| `src/app/features/booking/history-page.ts` and `.html` | Owner history/details, paging and cancellation confirmation |
| `src/app/features/booking/slot-admin-page.ts` and `.html` | Admin slot creation and capacity display |
| `src/app/features/booking/booking.scss` | Responsive shared layout and form styling |
| `src/app/app.routes.ts` | Signed-in visitor routes and administrator-only slot route |
| `proxy.conf.json` | Booking-specific requests to 8002; remaining Catalog API traffic to 8001 |
| `src/app/features/booking/booking-page.spec.ts` | Review, retry, conflict, stale response, status and cancellation tests |

The existing interceptor supplies Cognito access tokens to the configured API. Route guards improve navigation; Python independently verifies signatures, issuer, client, expiry and access-token purpose. The owner is always the JWT subject. `/me`, detail and cancellation filter by that subject. A different account receives 404 for another account's booking, including when the caller is an administrator.

The availability request counter prevents a slow response for an earlier date from replacing a newer date's slots. A busy state prevents duplicate button submits. Unknown outcomes retain the original request/key; conflicts unlock the form for a fresh reviewed attempt. Success displays the returned reservation status, including an expired/cancelled result from a later retry.

## 8. API contract

Open `http://127.0.0.1:8002/docs` for the generated schema. Every business endpoint needs a valid Cognito access token. Health endpoints are public. Never put tokens in URLs or commit them.

| Method and path | Access | Purpose |
|---|---|---|
| GET `/health/live` | Public | Process alive |
| GET `/health/ready` | Public | Booking tables accessible |
| GET `/api/v1/booking-policy` | Signed in | Park timezone, current date, final date, hold duration |
| GET `/api/v1/visit-slots?date=YYYY-MM-DD` | Signed in | Future slots and remaining guest places |
| POST `/api/v1/admin/visit-slots` | Administrator | Add a future non-overlapping slot |
| POST `/api/v1/bookings` | Signed in | Create/replay own reservation |
| GET `/api/v1/bookings/me?limit=20&offset=0` | Signed in | Own history; limit 1–100 |
| GET `/api/v1/bookings/{uuid}` | Owner | Own detail |
| POST `/api/v1/bookings/{uuid}/cancel` | Owner | Idempotent unpaid cancellation |

Create booking JSON, using real IDs returned by Catalog/slots and the current price version:

```json
{
  "tier_id": "<package UUID>",
  "slot_id": "<slot UUID>",
  "guest_count": 4,
  "expected_price_version": 1
}
```

Required headers: `Authorization: Bearer <access-token>`, `Content-Type: application/json`, `Idempotency-Key: <new UUID for this intended attempt>`. The placeholders above are explanatory and must be replaced before an API call. The client does not send visit times separately: the selected slot determines them.

Create slot JSON:

```json
{
  "visit_date": "2026-10-24",
  "start_time": "09:00",
  "end_time": "12:00",
  "capacity_guests": 4
}
```

Use a future date at demonstration time. Expected errors: 401 missing/invalid JWT; 403 visitor attempting admin creation; 404 missing/non-owned record; 409 overlap/full/stale price/reused key; 422 invalid date/time/count; 503 unavailable pricing or configuration/storage readiness. Business responses use `Cache-Control: no-store`.

## 9. Verify the implementation

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

This bootstraps separate Booking test schemas, checks Python lint/format, runs PostgreSQL integration tests for both services, runs Angular tests and builds Angular for production. Tests use `wonderland_test`; custom test URLs are rejected unless the database name ends `_test`. Ordinary tests roll back, and concurrent tests clean up their own generated test records.

Milestone verification on 15 October 2026: **89 Python tests and 32 Angular tests passed**, Python lint/format passed, production build passed. The initial Booking migration also passed a downgrade/upgrade cycle on the disposable test database, followed by the full Python suite. These are local checks; hosted GitHub Actions and cloud deployment remain separate work.

Key tests include two competing requests for the last places, concurrent identical retries producing one record, owner isolation even for another admin, signed JWT failures, fractional/bool/string guest rejection, stale price, rollback when outbox creation fails, cancellation/expiry releasing once and Booking's role being unable to read Catalog tables.

For your own demonstration:

1. Add a new future slot with capacity 4 outside the seeded windows.
2. Reserve Family for 4 people and check the admin screen shows 0/4 available and 4 held.
3. Reload history and open the reservation detail.
4. Cancel using the confirmation and verify 4/4 available and 0 held.
5. Keep the cancelled historical record as evidence.
6. For expiry, leave an unpaid hold for 30 minutes and refresh. Automated tests advance the clock without making the walkthrough wait.
7. Sign out and verify protected navigation requires login. With a separate visitor account, verify admin slot creation is denied and the first account's detail cannot be read.

The real walkthrough already created a Family reservation for 16 October and created/booked/cancelled a four-place slot for 24 October. The 24 October slot remains available for your practice. See `docs/evidence/step04-validation.md` and screenshots. The first reservation expires normally; screenshots capture its state at the time taken.

## 10. Troubleshoot and prepare the next milestone

| Symptom | Action |
|---|---|
| Booking path returns Catalog 404 | Restart Angular so its new proxy config loads |
| Network error after rebuild/start | Check `docker compose ps`; wait for API healthy, then reload options |
| No slots today | Choose tomorrow or add a future window as admin |
| Price changed (409) | Reload prices, review again and submit a new attempt |
| Full slot (409) | Reload availability or choose another window |
| 401/session expired | Sign out and sign in again; keep password entry in the app |
| Booking 503 | Check Booking `.env`, Catalog health and service logs |
| Holds seem stale | Refresh; inspect `docker compose logs --tail 50 booking-maintenance` |
| Role/schema missing on an old DB volume | Run `docker compose up booking-bootstrap`; migrations then create tables |
| Port already in use | Stop the host API or its container before starting the other |

Read logs with `docker compose logs --tail 50 booking catalog booking-maintenance`. Readiness checks storage, so a healthy Booking container alone does not prove Catalog pricing or Cognito connectivity; use the actual signed-in flow too.

Step 05 adds event delivery, publisher state/retries, queues, DLQs and consumer deduplication. Step 06 adds real sandbox payment and paid confirmation. Before connecting any provider, redesign expiry/cancellation to reconcile in-flight payments and late callbacks; this lesson's direct unpaid expiry must not release capacity for a payment whose outcome is unresolved. Add verified callbacks, transition guards, payment idempotency and ticket issuance together. Rate limits, paging/expiry batching at scale, production secrets/TLS and cloud deployment also remain future hardening work.

Stop with `scripts/stop-local.ps1` after closing host servers. The database volume is retained. Do not use volume deletion as a routine reset.
