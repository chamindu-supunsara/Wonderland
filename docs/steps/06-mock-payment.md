# Step 06 — Python mock checkout and Angular demonstration tickets

This implements the mock option you selected. It runs locally with your existing Cognito account, without AWS CLI credentials. Simulate success or failure, confirm guest places, view booking history and print one demonstration ticket per guest. No card information or money is involved.

This learning milestone does not complete the assignment's secure payment-provider integration requirement. Hosted sandbox checkout, verified callbacks, reconciliation and compensation/refunds remain future work. Guest references are demonstration references, not admission credentials or QR codes.

## 1. Run the project

Open PowerShell with Docker Desktop's Linux engine running:

```powershell
Set-Location D:\Courses\Microservices
docker compose up -d --build catalog booking booking-maintenance payment
docker compose ps
```

Compose prepares isolated roles/schemas, applies migrations, runs repeatable seeds and starts the services. It preserves edited prices and booking history. Do not remove the database volume.

In another terminal:

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Restart an existing Angular server with Ctrl+C first: the new proxy route requires a restart. These services have already been started in the current workspace.

On a fresh checkout, run `scripts\setup.ps1` first, then connect Cognito using Step 02. Stop host APIs before starting containers on the same ports.

| Component | Address | Check |
|---|---|---|
| Angular | http://127.0.0.1:4200 | Open /book |
| Catalog | http://127.0.0.1:8001 | /health/ready and /docs |
| Booking | http://127.0.0.1:8002 | /health/ready and /docs |
| MOCK Payment | http://127.0.0.1:8003 | /health/ready and /docs |
| PostgreSQL | 127.0.0.1:55432 | docker compose ps |

## 2. Configuration

The ignored `services/payment/.env` needs the same public Cognito settings as Booking:

```dotenv
DATABASE_URL=postgresql+psycopg://payment_dev:payment_dev_only@127.0.0.1:55432/wonderland
BOOKING_URL=http://127.0.0.1:8002
MOCK_PAYMENTS_ENABLED=true
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_aBuDlZ9RC
COGNITO_APP_CLIENT_ID=202ssal4mlube43ttm0j5m3k4i
```

The password above is the checked-in LOCAL database credential, not an AWS credential. Never put AWS keys or an app-client secret in Angular.

Both Payment and Booking require `MOCK_PAYMENTS_ENABLED=true`. Code defaults to false; local Compose explicitly enables both. In containers, Compose uses the database hostname `postgres` and Booking URL `http://booking:8000`. Avoid defining both service-specific database URL and DATABASE_URL; the service-specific variable has priority.

For host development, apply migrations through setup, stop the API containers, keep PostgreSQL and booking-maintenance running, set the mock flag in both service .env files, then run `scripts\start-backend.ps1`, `scripts\start-booking.ps1` and `scripts\start-payment.ps1` in separate terminals.

## 3. Create an unpaid reservation

1. Open http://127.0.0.1:4200/book and sign in with your existing Cognito account.
2. Choose a package and guests: Individual 1, Couple 2, Family up to 4, Group up to 5. Price is per package.
3. Choose a future date and future time slot. The seed adds the next seven days; use /admin/slots for other dates or a small-capacity demonstration.
4. Click **Review reservation**, check all details, then **Reserve pending payment**.
5. The booking is PENDING_PAYMENT and holds guest places for 30 minutes.
6. Click **Continue to mock checkout**.

Use a fresh reservation: old holds may have expired. Checkout retains the booking's price snapshot even if an administrator changes package pricing later.

## 4. Simulate success

1. Checkout says **LOCAL PAYMENT SIMULATOR** and displays the server-provided amount.
2. Click **Simulate success**.
3. Payment commits the immutable selected outcome as DECIDED before calling Booking.
4. Booking atomically converts held capacity to confirmed capacity, records its receipt, confirms the booking, issues one ticket per guest and writes a mock outbox event.
5. Checkout shows SUCCEEDED. Click **View demonstration tickets**.
6. For a four-guest Family booking, check four distinct MOCK references, numbered 1–4, with the right date and time.
7. **Print / save demonstration tickets** opens the browser print dialog. Choose Save as PDF yourself if wanted. Every printed ticket retains its demonstration disclaimer.
8. Open /bookings: the booking is **Confirmed · MOCK** and links to the same tickets. Reloading reads persisted tickets; it does not issue new ones.

Confirmed mock bookings cannot be cancelled through the unpaid-cancellation action. Paid cancellation/refund policy remains separate future work.

## 5. Simulate failure

1. Create a second new reservation and open checkout.
2. Click **Simulate failure**.
3. Payment becomes FAILED; Booking becomes PAYMENT_FAILED and releases held guest places.
4. No tickets are issued. Check history and availability.
5. To test success afterwards, create a new reservation. You cannot change a completed simulation result.

## 6. Test interruption, replay and expiry

A lost response does not prove settlement failed. Python may already have committed. Use **Retry same mock success/failure** with the existing checkout. The UI keeps the selected result; reloading restores the persisted decision. If authentication expired, sign in again and reopen checkout from history.

A unique checkout per booking, a unique Booking settlement receipt and slot locks make replay safe. The same completed success returns existing tickets without extra confirmed capacity or another confirmation event. An opposite outcome returns HTTP 409.

Leave an unpaid reservation for 30 minutes to test expiry. The maintenance worker or a history/availability refresh releases the hold. Late mock success is rejected with no tickets. A cancelled unpaid reservation is also rejected. A REJECTED checkout is terminal; create a new reservation.

Compare slot availability before and after: success keeps places occupied as confirmed; failure/cancellation/expiry releases them. Capacity counts people, not packages.

## 7. Understand the Python transaction

```text
Angular checkout
  -> Payment: independently verify Cognito token and booking owner
  -> Booking detail over HTTP: trusted price snapshot
  -> payment.mock_checkouts: READY -> DECIDED (commit)
  -> Booking mock settlement: independently verify token and owner
  -> one Booking transaction:
       receipt + status + capacity + guest tickets + mock outbox event
  -> Payment: SUCCEEDED / FAILED / REJECTED
  -> Angular history and demonstration tickets
```

Payment has its own database role/schema and cannot read Booking tables. The caller token is forwarded to the configured Booking URL for that request and never persisted. Browser-supplied totals are rejected. An administrator still only sees their own checkouts/tickets. Guessing another user's ID returns 404. API responses use Cache-Control: no-store.

All Booking capacity changes lock the slot before changing its booking. Settlement also serializes reuse of a checkout ID. A failed transaction rolls back tickets, receipt, counters and event together.

| File | Purpose |
|---|---|
| services/payment/payment_app/main.py | Checkout, immutable decision, HTTP settlement and retry |
| services/payment/payment_app/auth.py | Independent Cognito JWT verification |
| services/payment/payment_app/models.py | Payment-owned persisted checkout |
| services/payment/alembic/versions/0001_mock.py | Payment migration |
| services/booking/booking_app/mock_checkout.py | Atomic settlement and owner ticket API |
| services/booking/alembic/versions/0003_mock_checkout.py | New statuses, receipts and guest tickets |
| frontend/src/app/features/booking/checkout-page.* | Checkout UI and recovery |
| frontend/src/app/features/booking/guest-tickets-page.* | Guest ticket page and print styles |
| frontend/src/app/features/booking/history-page.* | New status and action links |
| frontend/proxy.conf.json | Payment requests to port 8003 |
| deploy/local/postgres/005-payment.sql | Separate development/test roles and schemas |

## 8. API contract

All these routes require a valid Cognito access token. Use Angular for the walkthrough; do not share tokens in chat.

| Method | Route | Body / result |
|---|---|---|
| POST | /api/v1/payments/checkouts | { "booking_id": "UUID" }; create/reuse checkout |
| GET | /api/v1/payments/checkouts/{id} | Owner's persisted result |
| POST | /api/v1/payments/checkouts/{id}/complete | { "outcome": "success" } or "failure" |
| POST | /api/v1/bookings/{id}/mock-payment | Mock-only checkout UUID + outcome |
| GET | /api/v1/bookings/{id}/tickets | Owner's confirmed demonstration tickets |

Booking statuses: PENDING_PAYMENT, CONFIRMED, PAYMENT_FAILED, CANCELLED, EXPIRED.
Checkout statuses: READY, DECIDED, SUCCEEDED, FAILED, REJECTED.

## 9. AWS events boundary

Booking writes **MockBookingConfirmed** or **MockBookingPaymentFailed**, with payment_mode=MOCK, to its transactional outbox. Analytics recognizes these and requires the mock label. They must never count as real collected revenue.

This local flow uses HTTP between Payment and Booking. It does not consume the Step 05 Payment queue, start continuous AWS workers or resolve the pending non-root IAM Identity Center login. Outbox records stay durable until a publisher runs. The local walkthrough works independently of that AWS setup.

## 10. Verify and troubleshoot

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Tests use wonderland_test, preserving development data. They check ownership, duplicate suppression, immutable outcome, unknown-response retry, expired/cancelled rejection, atomic rollback, per-guest tickets, capacity and database isolation, plus existing features. Angular checks success/failure/retry behavior; verification also runs lint, formatting and the production build. See [validation evidence](../evidence/step06-validation.md).

| Symptom | Action |
|---|---|
| Checkout load error | Check sign-in, service health and reservation ownership |
| Mock endpoint 404 | Check mock flag in both APIs, restart/rebuild; IDs also remain owner-filtered |
| Payment requests reach Catalog | Restart Angular for its new proxy route |
| 401 | Sign in again; check matching public Cognito configuration |
| 503 / unknown result | Restore connectivity and retry SAME checkout/outcome |
| REJECTED | Refresh booking; create a new reservation if expired/cancelled |
| No slots | Choose a seeded future date or add a slot as admin |
| Missing table | Check docker compose logs payment-migrate booking-migrate; rerun startup |

Stop Angular with Ctrl+C, then run scripts\stop-local.ps1 to preserve the database volume.

Next: **Step 07 Admission** — separate Python service, protected staff screen, independent ticket projection, duplicate-safe guest check-in, timestamped ride usage and visitor visit history. Mock admission demonstrations must also remain clearly labelled as simulations.

