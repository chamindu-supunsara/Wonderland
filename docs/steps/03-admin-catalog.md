# Step 03 — Protected attractions and ticket pricing

This milestone is implemented in your existing Python/Angular project. Follow this lesson to understand the code and repeat the workflow yourself. It reuses your Mumbai Cognito user pool and administrator account. Catalog data is stored in your local PostgreSQL database; cloud hosting comes later.

## 1. Understand the completed slice

At `/admin`, an administrator can add attractions, edit active attractions, retire them, search/filter records, publish package prices, inspect every price version, and view recent successful changes. Visitors retain public attraction and ticket browsing. Every administrator endpoint independently checks the verified Cognito access token and `Administrators` membership.

The four existing packages remain Individual, Couple, Family and Group. Their codes, names, guest limits and USD currency are fixed in this lesson. You manage each package's price. Creating/removing packages, reactivating retired attractions, scheduling slots and booking are outside this milestone; slots and capacity belong to Step 04. These are implementation boundaries, not claims that all assignment work is complete.

## 2. Start the application

Open Docker Desktop and wait until its Linux engine is running. In PowerShell:

```powershell
Set-Location D:\Courses\Microservices
docker compose up -d --build catalog
docker compose ps
```

This starts PostgreSQL, applies Alembic migrations, runs the repeatable seed and starts FastAPI on port 8001. The additive migration has already been applied on this machine. Running the command again preserves edited data and price history. Do not run a host Python API on the same port at the same time.

In another terminal:

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

If Angular is already running at port 4200, use that process. Open [administrator catalog](http://127.0.0.1:4200/admin). Sign in yourself if prompted. Use `127.0.0.1` consistently because browser authentication storage is origin-specific.

For host Python development instead of the containerized API:

```powershell
Set-Location D:\Courses\Microservices
docker compose stop catalog
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

The host startup script starts Uvicorn with reload against the already migrated database. Use the Compose command above first when a migration changes. Stop Uvicorn with Ctrl+C before returning to the container API. Python source edits need a container rebuild when using Docker; Angular development reloads its source automatically.

## 3. Learn the file structure in dependency order

| File, relative to repository | Purpose |
|---|---|
| `services/catalog/app/models.py` | Database tables and constraints |
| `services/catalog/alembic/versions/0002_admin_catalog.py` | Upgrade existing storage without resetting it |
| `services/catalog/app/admin_schemas.py` | Strict write validation and administrator response models |
| `services/catalog/app/api/admin.py` | Protected reads, transactional writes, locking and audit |
| `services/catalog/app/main.py` | Registers the router, write CORS methods and storage readiness checks |
| `services/catalog/app/seed.py` | Stable seed identity, preserving renamed/retired attractions |
| `frontend/src/app/core/api/admin-api.ts` | Typed HTTP calls and exact decimal-to-cents conversion |
| `frontend/src/app/features/admin/admin-page.ts` | Screen state, form actions and error handling |
| `frontend/src/app/features/admin/admin-page.html` | Labeled forms, confirmation steps, history and activity |
| `frontend/src/app/features/admin/admin-page.scss` | Existing park theme and responsive layout |
| `frontend/src/app/app.routes.ts` | Administrator guard and lazy loading |
| `services/catalog/tests/test_admin.py` | Database/API authorization, writes, rollback and concurrency tests |
| `frontend/src/app/features/admin/admin-page.spec.ts` | Form, confirmation, conflict and history loading tests |

Read the existing `app/auth.py`, Angular auth guard and interceptor from Step 02 before the new routes. `/admin/access-check` now holds the earlier administrator identity verification screen; `/admin` is the actual management dashboard. `/account` still verifies the signed-in user's Python API access.

## 4. Understand the database upgrade

Attractions gain `revision`, initially 1, and a unique nullable `seed_key`. Each successful edit or first retirement increments the revision. The stable seed key prevents startup from recreating a seed attraction after its display name changes. Migration 0002 backfills keys for the four original records.

Ticket prices gain `created_by`, which records the verified administrator subject for new versions. Existing prices have no actor and are labeled initial catalog. The existing unique `(tier_id, version)` constraint and partial unique index for one active price per tier remain in use.

`catalog.audit_events` stores a UUID, actor, action, resource UUID, timestamp and JSON before/after snapshots. Audit writes commit in the same transaction as the domain change. There is no public audit endpoint and no audit editing/deletion API. This is an application audit trail; stronger database privileges and retention controls are future cloud hardening.

Readiness queries the new columns and audit table. An API with missing Step 03 storage returns 503 rather than reporting healthy storage.

## 5. Add an attraction yourself

1. Open `/admin` and select **Attractions**.
2. Click **+ Add attraction**.
3. Enter a meaningful name, description and visitor guidance.
4. Select category and thrill level.
5. Enter minimum age/height only where applicable. An empty value means no minimum specified; age and height must be whole numbers.
6. Click **Save attraction** once. Wait for the success message and the new card.
7. Open [public browsing](http://127.0.0.1:4200/) and verify the attraction appears. Public pages refetch on loading; already-open pages need refresh.

| Field | API rule |
|---|---|
| Name | Trimmed, nonblank, at most 120 characters |
| Description | Trimmed, nonblank, at most 5,000 characters |
| Category | `ROLLER_COASTER`, `KIDS`, `WATER`, `INTERACTIVE` |
| Thrill | `LOW`, `MEDIUM`, `HIGH` |
| Minimum age | Null or whole number 0–120 |
| Minimum height | Null or whole number 0–300 cm |
| Visitor guidance | Trimmed, nonblank, at most 2,000 characters |

Angular prevents common invalid input; Python enforces the rules again. Unknown request fields are rejected. An API caller cannot submit its own status, revision, creator or role when creating an attraction. Suitability limits and text limits are project validation policies.

Example POST body for learning (the screen sends it automatically):

```json
{
  "name": "Discovery Garden",
  "description": "Explore playful challenges together.",
  "category": "INTERACTIVE",
  "thrill_level": "LOW",
  "min_age": null,
  "min_height_cm": null,
  "guidance_text": "Young children should have adult supervision."
}
```

## 6. Edit an active attraction

Search for the record, click its **Edit** button, change the fields in the editor above the list and save. Angular sends all editable fields plus `expected_revision` from the card. PostgreSQL locks that row, checks the revision, applies the edit, increments the revision and saves its audit record atomically.

For example, two administrators both load revision 1. The first save commits revision 2. The second save with expected revision 1 receives `409 Conflict`, leaving the first update intact. The screen keeps the failed form so you can copy any useful text. **Reload latest data (discard form)** explicitly clears the form and loads the current record; inspect the newer content before editing again.

The transaction boundary is `with session.begin()`. SQLAlchemy commits on successful exit and rolls back when an exception escapes. See the official [session transaction guide](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) and [`with_for_update` documentation](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.Select.with_for_update) for the mechanisms used here.

## 7. Retire an attraction

1. Use a learning/demo record for your first retirement.
2. Click **Retire [name]** and read the inline confirmation.
3. Click **Confirm retirement**.
4. Set **Show status** to **Retired**. The retained card is read only and its revision increased.
5. Refresh public browsing: the attraction disappears. Its public detail endpoint also returns 404.
6. Open **Recent activity** to see creation, edit and retirement events.

Retirement sets `status = RETIRED`; it keeps the UUID, content and audit history. There is no hard-delete endpoint. Reactivation is not exposed in this step. Decide carefully before retiring a real attraction; restarting/seeding does not reactivate it.

## 8. Change package pricing

1. Select **Ticket pricing**.
2. Select Individual, Couple, Family or Group.
3. Inspect the current amount, currency, version and price history.
4. Enter the new package amount, for example `42.50`.
5. Click **Review price change** and check the old/new amounts.
6. Click **Publish price** once and wait for success.
7. Verify the new current version and retained earlier versions.
8. Refresh [public ticket tiers](http://127.0.0.1:4200/tickets) to see the current amount.

Prices are fixed per package, not multiplied by guest count. Individual permits 1 guest; Couple 2; Family 1–4; Group 1–5 under the project's existing interpretation of “up to.” Booking guest validation will be implemented next.

Angular converts the decimal string into integer cents without multiplying a parsed floating-point amount: `42.50` becomes `4250`. Python accepts only a strict integer from 1 through 100,000,000 cents. The UI allows 0.01–1,000,000.00 USD and at most two decimal places; negative/zero amounts, exponent notation and fractional cents are rejected. The upper bound is a project policy. The API preserves USD currency and refuses a publication with the same amount as the current price.

Example publication body:

```json
{"amount_minor": 4250, "expected_version": 1}
```

The backend locks the stable tier row, checks the current version, marks the previous price inactive, flushes that update, inserts version 2 and records an audit event, all in one transaction. Flushing the inactive flag before insertion satisfies the unique active-price index. Competing requests with the same expected version produce one success and one conflict. A transaction failure leaves the original active price intact.

To restore an old amount, publish that amount again. History remains, for example version 1 = $40, version 2 = $42.50, version 3 = $40. Earlier amounts are never overwritten by the API. Future bookings must snapshot tier, guest count, amount, currency and price version; this milestone does not implement bookings or pricing events.

## 9. Review activity and API contracts

**Recent activity** displays the latest 30 successful catalog changes, with action, timestamp, resource ID and verified actor subject. The stored JSON additionally preserves before/after values. Failed validation, denied access and conflicts do not produce successful-change audit events. Security failure logging/monitoring is a separate future concern.

All routes below begin with `/api/v1/admin` and require a valid administrator access token:

| Method | Path | Result |
|---|---|---|
| GET | `/attractions?status=ALL` | All records; optional ACTIVE/RETIRED filter |
| POST | `/attractions` | Creates attraction, 201 |
| PUT | `/attractions/{id}` | Full editable content plus expected revision, 200 |
| POST | `/attractions/{id}/retire` | Expected revision, retirement, 200 |
| GET | `/ticket-tiers` | Package metadata and current prices |
| GET | `/ticket-tiers/{id}/prices` | Every price version, newest first |
| POST | `/ticket-tiers/{id}/prices` | Integer cents plus expected version, 201 |
| GET | `/audit` | Latest 30 events; optional `resource_id` and `limit` 1–100 |

Use [local OpenAPI](http://127.0.0.1:8001/docs) to inspect schemas. Do not put access tokens into documentation, screenshots or source control. The existing interceptor adds a token only to the configured API origin/path. Angular's guard handles navigation; Python's router dependency enforces access independently of the UI.

## 10. Test the milestone

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

This checks Python lint/format, the separate PostgreSQL test database, Angular tests and the production build. Tests migrate/seed `wonderland_test`, never reset the development catalog, and reject a test database name without `_test`. Normal test writes roll back. The concurrent test commits a disposable tier into the test database and cleans up its exact generated ID afterward.

Coverage includes anonymous 401 and visitor 403 on all administrator routes, valid admin writes, validation, stale revisions, read-only retired records, old price preservation, competing price writes, transaction rollback on audit failure, stable seed identity, Angular confirmations, conflict form preservation, exact cents conversion and stale history-response handling.

For a manual security check, use a separate visitor account/browser session and open `/admin`: it must deny access. The automated Python suite also calls the API directly with visitor identity, so hiding buttons is not the security test. Your real administrator session was exercised through the complete add/edit/retire and price publication workflows. See [validation and screenshots](../evidence/step03-validation.md).

## 11. Troubleshoot deliberately

| Symptom | Action |
|---|---|
| Redirect to login | Sign in in this exact origin/tab. A new tab may not share session storage. |
| 401 | Sign out/in; confirm the runtime configuration still targets the Step 02 Cognito pool/client. |
| 403 | Confirm intended Administrators membership and obtain a fresh session after membership changes. |
| 404 on retired public detail | Expected: public browsing only exposes active attractions. |
| 409 | A newer revision/version exists, the record is retired/inactive, or the amount is unchanged. Reload and review. |
| 422 | Check text lengths, required content, enum codes, integers and price bounds. |
| Network error/timeout after saving | Reload before retrying and inspect records/history/activity; the server may have committed even if the response was lost. |
| Missing column/table or readiness 503 | Rebuild/start Catalog so migration 0002 runs. Inspect `docker compose logs catalog-migrate catalog`. |
| Backend source change appears ignored | Rebuild the API container, or use the host reload workflow. |
| Port 8001 or 4200 already used | Reuse the existing intended process or stop its terminal before starting another. |

Do not erase the database volume to resolve a migration or authentication issue. Audit history is retained local data. Container stops preserve the volume.

## 12. Check your understanding before Step 04

Explain why the API checks roles even with an Angular guard; why a retirement preserves a record; why expected revisions are checked under a row lock; why cents are integers; why price changes create versions; and why audit and data commit together. Trace one create request from the Angular form through the typed client, auth interceptor, Python dependency, schema, transaction and PostgreSQL row.

Next, Booking will add visit dates/slots, atomic capacity, authenticated ownership, idempotency and price snapshots. Cloud deployment, SNS/SQS events, payments, admission and analytics still have their own roadmap milestones.
