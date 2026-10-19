# Step 07 — Mock guest admission and ride usage (Python + Angular)

This step adds a separate Python Admission API, an administrator staff screen, per-guest mock check-in, timestamped ride usage and owner-filtered visit history. It works with your Step 06 demonstration tickets. Every screen and event remains explicitly MOCK.

The assignment checklist describes the assessed requirements. The simulation-time policy below is our implementation choice for this learning milestone. It does not represent real arrivals, paid park admission, hardware scanning, or production safety checks.

## 1. What is built

| Area | Implementation |
|---|---|
| Staff access | Existing Cognito Administrators group, Angular administrator guard, independent Python JWT/role checks |
| Ticket verification | Protected Booking HTTP lookup; only CONFIRMED / MOCK guest tickets accepted |
| Admission storage | Isolated admission database schema and development/test roles |
| Guest entry | One persisted check-in per guest ticket, safe under concurrent repeats |
| Ride usage | Requires check-in, active Catalog attraction and valid simulation time |
| Retry safety | UUID Idempotency-Key, persisted request hash, exact replay; pending browser request survives reload |
| Visit history | Booking owner sees each guest entry and paginated ride usage |
| Events | MockGuestCheckedIn and MockRideUsed stored atomically in a local transactional outbox |
| Audit times | Simulated occurred_at and actual server recorded_at retained separately |

The staff screen uses the existing administrator role. No additional AWS permissions, IAM users, Cognito groups or AWS resources were created.

## 2. Start everything

Open PowerShell with Docker Desktop running its Linux engine:

```powershell
Set-Location D:\Courses\Microservices
docker compose up -d --build catalog booking booking-maintenance payment admission
docker compose ps
```

Compose runs repeatable service bootstraps, migrations and seeds. Existing bookings, prices and demonstration tickets stay in the database. Do not remove the database volume.

In a second terminal:

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Restart an existing Angular server with Ctrl+C first: the Admission proxy route requires a restart. The services and Angular have already been started in this workspace.

| Component | Address |
|---|---|
| Angular | http://127.0.0.1:4200 |
| Staff mock admission | http://127.0.0.1:4200/admin/admission |
| My simulated visits | http://127.0.0.1:4200/visits |
| Admission API docs | http://127.0.0.1:8004/docs |
| Admission readiness | http://127.0.0.1:8004/health/ready |
| Booking / Payment | Ports 8002 / 8003 |
| Catalog | Port 8001 |
| PostgreSQL | Loopback port 55432 |

For a fresh checkout, run scripts/setup.ps1 first and complete Step 02 Cognito configuration. scripts/connect-cognito.ps1 now updates Catalog, Booking, Payment and Admission together. It only writes public identifiers; passwords and AWS credentials do not belong in these files.

## 3. Check configuration

Local, ignored services/admission/.env uses:

```dotenv
DATABASE_URL=postgresql+psycopg://admission_dev:admission_dev_only@127.0.0.1:55432/wonderland
MOCK_ADMISSION_ENABLED=true
BOOKING_URL=http://127.0.0.1:8002
CATALOG_URL=http://127.0.0.1:8001
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_aBuDlZ9RC
COGNITO_APP_CLIENT_ID=202ssal4mlube43ttm0j5m3k4i
```

The password shown is the checked-in LOCAL development credential, not an AWS credential. Do not commit .env or put secrets in Angular.

Code defaults MOCK_ADMISSION_ENABLED to false. Local Compose explicitly enables it, uses the internal database host postgres and URLs http://booking:8000 and http://catalog:8000. Booking also needs its Step 06 MOCK_PAYMENTS_ENABLED=true flag for the protected mock-ticket lookup. No real admission mode exists in this service.

Use DATABASE_URL or ADMISSION_DATABASE_URL consistently; the service-specific variable wins if both exist. Keep Admission on its own database role.

For host hot reload: run setup/migrations, stop the admission API container, retain PostgreSQL and the other APIs, then run scripts/start-admission.ps1. Do not run both host and container APIs on port 8004. Source edits to containerized services require a rebuild.

## 4. Prepare a confirmed mock ticket

1. Sign in to Wonderland as a visitor or administrator.
2. Open /book and reserve a future date/slot with available guest capacity.
3. Continue to mock checkout and choose Simulate success.
4. Open the demonstration ticket page from /bookings.
5. Copy one guest's full MOCK- reference. Use the guest reference, not the WL- booking reference.
6. For a Family package, each of the four guest tickets has an independent check-in. The booking owner's account sees their visits.

You can use an existing Step 06 confirmed booking. Pending, expired, cancelled or failed bookings cannot supply an accepted confirmed mock ticket. A purchaser's administrator status does not make an unpaid reservation admissible.

## 5. Sign in as staff and look up the guest

1. Use the existing administrator account.
2. Open /admin, then Mock guest check-in and ride usage, or visit /admin/admission directly.
3. Paste the guest reference into Guest demonstration ticket reference.
4. Click Look up ticket.
5. Check the package, booking reference, guest number and visit slot against the guest's demonstration ticket.
6. Admission calls Booking with the caller's token. Booking independently requires administrator membership and returns a confirmed mock snapshot. The browser cannot supply an owner or confirmation flag.
7. The screen shows whether this particular guest has already checked in.

A normal visitor is blocked from staff pages and staff API writes. Knowing a reference alone is not sufficient.

## 6. Simulate guest check-in

1. Choose Simulated visit time (Asia/Colombo). It defaults to the booked slot start.
2. Choose a time inside that slot. For 09:00–12:00, 09:00 is allowed and 12:00 is excluded.
3. Click Simulate guest check-in.
4. Check the success message and recorded check-in time.
5. Click Verify duplicate check-in. It returns the existing entry and says no duplicate entry was recorded.
6. Look up the next guest reference to check in another person.

You can test tomorrow's booking today because the input is explicitly a simulation time. Python separately records the actual audit time. The application does not change its system clock or pretend a simulated arrival is a real one.

This milestone permits one check-in per ticket; re-entry and exit tracking are outside this step. Admission does not increment Booking capacity: Step 06 already confirmed those places. Keeping entry counts separate prevents double counting.

## 7. Record mock ride usage

1. Look up a guest who has checked in.
2. Set a simulated ride time at or after check-in and before the slot end.
3. Select an active ride/attraction from Catalog.
4. Check the guest reference and attraction.
5. Click Record mock ride usage once.
6. Confirm the success message, increased ride count and recent ride list.
7. For a separate ride, choose the desired attraction/time and submit again. A deliberate new submission has a new retry key and counts as another ride use.

The server independently fetches the active-only attraction endpoint before a new write. A retired/unknown attraction or unavailable Catalog does not create a ride record. Historical ride facts retain the attraction name/category recorded at that time.

Staff remain responsible for age, height and suitability decisions. The screen records simulated usage; it does not implement physical barriers, sensors, queue capacity, ride safety enforcement or guest age/height profiles.

## 8. Handle an interrupted request safely

If a response is lost, the ride might already be committed. Do not start a different submission to guess its result.

- The screen keeps the exact guest, attraction, time and retry UUID.
- Editable fields are locked while the result is unresolved.
- Use Retry same mock ride.
- If the page reloads in the same browser tab, the staff-account-scoped session storage restores the pending request and reloads its guest.
- If guest loading failed, use Resume pending guest, then retry.
- A 401/403 or service outage preserves the pending request. Restore the same account/session and retry.
- A definite validation/not-found/conflict rejection releases the form for correction.
- After success, the pending request is cleared. A new submission means a separate ride.

Keep the same tab/session until an uncertain request is resolved. Do not clear session storage or move to another browser during recovery. No token or password is stored in this retry record.

On the server, the same staff account + key + payload returns the existing ride. Reusing the key for different input returns 409. Concurrent requests serialize and cannot create duplicate facts/events. This protects transport retries; it cannot infer whether two intentionally separate submissions describe the same physical ride.

## 9. View the booking owner's history

1. Sign in as the account that owns the booking.
2. Open My visit history from /account or /bookings, or visit /visits.
3. Each guest check-in appears separately with MOCK, simulated check-in time and actual recorded time.
4. Click View ride history for the desired guest.
5. Check attraction, category and simulated time.
6. Use Previous/Next visits and Previous/Next rides to paginate. Refresh visits reloads the current visit page.

An administrator's personal history still only shows their own booking's guests. Another owner's visit ID returns 404 on the visitor history endpoint. Staff use the dedicated staff lookup to operate on another customer's guest ticket.

## 10. Understand the service boundary

```text
Angular administrator screen
  -> Admission: verify Cognito administrator
  -> Booking protected lookup: independently verify administrator
       -> accept only confirmed MOCK ticket
  -> Admission transaction:
       trusted local ticket projection + unique check-in + MockGuestCheckedIn outbox

Angular ride submission + stable UUID retry key
  -> Admission: verify administrator and prior retry
  -> Catalog: require current active attraction for a new ride
  -> Admission transaction:
       lock guest entry + validate time + insert ride + increment event version
       + MockRideUsed outbox

Angular owner visit history
  -> Admission: verify current user + filter projected booking owner
```

The local ticket projection is pulled from Booking over authenticated HTTP when staff check in a guest. It is not an SNS-fed projection in this milestone. Admission never reads Booking, Catalog or Payment database tables. Existing check-in/ticket snapshots must remain consistent; an unexpected changed snapshot is rejected for investigation.

Booking lookup failure prevents a new entry. Catalog failure prevents a new ride. Persisted owner history continues to work without calling either upstream. Replays of an already recorded ride work even if its attraction has since retired.

## 11. Database and source files

| Table | Purpose |
|---|---|
| admission.ticket_projection | Verified ticket/owner/slot snapshot; no cross-service database foreign key |
| admission.check_ins | One row per ticket, staff actor, simulated/actual times, event version |
| admission.ride_uses | One row per deliberate ride, attraction snapshot, actor/key/hash and timestamps |
| admission.outbox_events | Atomic mock facts, unique aggregate/version and future delivery metadata |

The development schema is owned by admission_dev; tests use admission_test in wonderland_test. Cross-service database access is denied. Check-in uses an advisory ticket lock and database uniqueness; ride writes serialize by retry key and lock the guest entry before changing its event version. Failure rolls back the fact and outbox together.

| File | Purpose |
|---|---|
| services/admission/admission_app/main.py | Staff/owner API routes, transactions, validation and events |
| services/admission/admission_app/auth.py | Independent Cognito verification and administrator dependency |
| services/admission/admission_app/upstream.py | Bounded/time-limited trusted Booking/Catalog calls, validated snapshots |
| services/admission/admission_app/schemas.py | Strict request shapes, timezone-aware timestamps, UTC normalization |
| services/admission/admission_app/models.py | Admission-owned tables |
| services/admission/alembic/versions/0001_mock_admission.py | Database migration |
| deploy/local/postgres/006-admission.sql | Repeatable local roles/schemas |
| services/booking/booking_app/main.py | Protected confirmed mock-ticket export |
| frontend/src/app/core/api/admission-api.ts | Typed API client |
| frontend/src/app/features/admission/staff-page.* | Protected mock staff workflow |
| frontend/src/app/features/admission/visit-history-page.* | Owner history and ride pagination |
| frontend/proxy.conf.json | Admission requests to port 8004 |
| scripts/start-admission.ps1 | Optional host hot reload |

## 12. API contract

All business endpoints require a valid Cognito access token. Use Angular for the walkthrough; never send tokens through chat.

| Method | Endpoint | Access |
|---|---|---|
| GET | /api/v1/admissions/staff/tickets/{MOCK-reference} | Administrator |
| POST | /api/v1/admissions/staff/check-ins | Administrator |
| POST | /api/v1/admissions/staff/ride-uses | Administrator + UUID Idempotency-Key header |
| GET | /api/v1/admissions/visits/me?limit=20&offset=0 | Booking owner |
| GET | /api/v1/admissions/visits/{id}/rides?limit=20&offset=0 | Booking owner |
| GET | Booking /api/v1/admin/mock-tickets/{reference} | Administrator, Booking mock mode enabled |

Example check-in body:

```json
{
  "ticket_reference": "MOCK-<32 uppercase hexadecimal characters>",
  "simulation_time": "2026-10-16T09:00:00+05:30"
}
```

Ride usage adds attraction_id (UUID) and requires Idempotency-Key in the header. Guest reference placeholders must be replaced with an actual issued reference.

New entry/ride returns 201; an idempotent repeat returns 200. Missing authentication returns 401; a visitor staff request returns 403; unknown/other-owner resources return 404; conflicting retry/absent check-in returns 409; invalid time/input returns 422; upstream failure returns 503. Business responses carry Cache-Control: no-store.

Input timestamps must include a timezone. The Angular datetime-local input is explicitly converted from Asia/Colombo (+05:30) to UTC regardless of the computer's own timezone. No client-supplied audit timestamp or actor ID is accepted.

## 13. Events, analytics and AWS limits

Each accepted entry creates MockGuestCheckedIn; each ride creates MockRideUsed. Payloads contain mode=MOCK, stable guest/admission identifiers, simulated occurred_at and actual recorded_at. Per-entry event versions increase monotonically. The outbox transaction is tested for rollback and duplicate safety.

These Admission events are **stored locally only**. This step does not add an Admission SNS topic, queue, IAM publisher role, consumer or BI dashboard. The shared Step 05 event transport currently recognizes Catalog/Booking sources; it must be explicitly extended before publishing Admission events. Do not point the Booking publisher at this schema.

Step 05 continuous workers still await the correct non-root AWS SSO setup. That does not block this mock Admission workflow. Step 08 will use these distinct mock facts to build reporting and extend delivery; simulated counts must not be reported as real attendance or revenue.

## 14. Verify and inspect

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

This prepares test schemas and runs Python lint/format, PostgreSQL integration tests, Angular tests and production build. Tests reject a database name that does not end in _test and preserve development data.

The suite covers independent signed JWT validation, role/owner denial, disabled mock mode, time boundaries/timezone requirements, upstream rejection, independent guest check-in, concurrent duplicate entry/ride requests, idempotency conflicts, deliberate repeat rides, atomic outbox rollback, active/retired attractions, history and database isolation. Angular tests cover Colombo conversion, duplicate messaging, required check-in, reload recovery, rejected inputs and history.

Read-only local event inspection:

```powershell
docker compose exec -T postgres psql -U admission_dev -d wonderland -c "SELECT event_type,payload->>'mode' AS mode,count(*) FROM admission.outbox_events GROUP BY 1,2;"
```

See [Step 07 evidence](../evidence/step07-validation.md) for actual automated results, browser records and screenshots.

## 15. Troubleshooting and finish checklist

| Symptom | Fix |
|---|---|
| Staff route redirects / 403 | Use the existing administrator account; refresh Cognito session after any group changes |
| 404 mock endpoint | Enable mock flags in Admission and Booking; restart/rebuild both |
| Ticket not found | Use a per-guest MOCK reference from a confirmed mock booking |
| No ticket card / 503 | Check Booking health, matching Cognito IDs and service URLs |
| Admission requests reach Catalog | Restart Angular for its new proxy configuration |
| Ride says check in first | Look up and check in that guest reference, not another member of the party |
| 422 time | Choose a timezone-aware time inside the slot, at/after guest check-in |
| Active attraction rejected | Refresh Catalog; retired attractions cannot receive new uses |
| Pending request after reload | Same staff account/tab: Resume pending guest, then Retry same mock ride |
| Empty own history | Only checked-in guests from your own bookings appear; refresh and check the account |
| Missing table | Inspect docker compose logs admission-migrate and rerun startup |

Practice: create a fresh confirmed mock booking, check in guest 3 or 4, verify duplicate entry, record one ride, try an invalid time, and find the guest in owner history. Leave each deliberate demo record intact as evidence.

Stop Angular with Ctrl+C, then scripts/stop-local.ps1 to stop containers while preserving the volume.

Next milestone: Step 08 Analytics and Metabase — durable mock fact delivery, reporting views, guest arrivals by time, rides by popularity and connected dashboards, with mock data clearly separated from any future real financial/attendance facts.

