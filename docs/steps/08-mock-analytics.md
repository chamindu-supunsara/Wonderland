# Step 08 — Mock Analytics and connected Metabase dashboards

This step implements guest arrivals, popular rides and peak/quiet times using your mock Admission events. A Python worker delivers durable events into independent Analytics facts. Metabase reads aggregate reporting views through a restricted account.

The dashboards are working locally. They report simulated activity only. They do not establish real attendance, purchases, revenue, physical occupancy or real-world operating hours.

## 1. Start the project

With Docker Desktop's Linux engine running, open PowerShell:

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\start-analytics.ps1
```

The script starts Catalog, Booking, mock Payment, mock Admission, the expiry worker, Analytics and Metabase. Compose applies repeatable bootstraps and migrations before the worker starts.

Equivalent command:

```powershell
docker compose up -d --build catalog booking booking-maintenance payment admission analytics-mock metabase
docker compose ps
```

In another terminal, start Angular:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Do not start a second Angular process if port 4200 is already occupied. For a fresh checkout, run scripts/setup.ps1 and complete the Cognito setup first.

| Component | URL / role |
|---|---|
| Angular app | http://127.0.0.1:4200 |
| Mock staff admission | http://127.0.0.1:4200/admin/admission |
| Metabase | http://127.0.0.1:3000 |
| Operations dashboard | http://127.0.0.1:3000/dashboard/2-wonderland-mock-operations |
| Pipeline health dashboard | http://127.0.0.1:3000/dashboard/3-wonderland-mock-pipeline-health |
| PostgreSQL | 127.0.0.1:55432 |
| Mock Analytics worker | Docker analytics-mock, polls every 5 seconds |

Dashboard IDs above belong to this local instance. On a new Metabase application database, IDs can differ; find the dashboards by name.

## 2. Understand the two Metabase database connections

Metabase's own settings and the data it reports are separate:

| Connection | Database / user | Purpose |
|---|---|---|
| Application metadata | wonderland_metabase / metabase_app | Local login, saved questions, dashboards and settings |
| Reporting data | wonderland / metabase_reader | SELECT on aggregate reporting views only |

The app database is PostgreSQL, retained in the existing named PostgreSQL volume. Stop/restart preserves dashboards. Avoid docker compose down -v: that deliberately erases the volume and all application data.

The image is pinned to metabase/metabase:v0.64.1.x. The official Docker and application-database setup is described in [Metabase Docker documentation](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker) and [application database documentation](https://www.metabase.com/docs/latest/installation-and-operation/configuring-application-database).

## 3. First-time Metabase login and connection

This was completed during the walkthrough. For a fresh Metabase database:

1. Open http://127.0.0.1:3000 and choose Let's get started.
2. Enter your account details and create your password directly in Metabase.
3. Complete setup. You can skip adding data until the account is ready.
4. Use Add your data and select PostgreSQL.
5. Enter the following LOCAL connection values.
6. Save and verify that Metabase says Connected.

| Field | Value |
|---|---|
| Display name | Wonderland MOCK Reporting |
| Host | postgres |
| Port | 5432 |
| Database name | wonderland |
| Username | metabase_reader |
| Password | metabase_reader_only |
| Schemas | reporting, or All (the role can only read the granted reporting views) |

These are checked-in LOCAL development database credentials. They are not AWS credentials or your Metabase login. The host is postgres because Metabase runs inside Docker; do not use the host-mapped 55432 port for this internal connection.

Metabase login is separate from Cognito. The Angular administrator area links to Metabase; it does not embed it or provide SSO. Both services bind to loopback. Public sharing, anonymous access, email subscriptions and cloud hosting are not configured.

## 4. Open and read the Operations dashboard

Open Wonderland MOCK Operations. It contains four saved questions:

1. **MOCK - Daily guest arrivals:** one checked-in guest ticket counts once, grouped by simulated visit date.
2. **MOCK - Popular rides:** deliberate recorded ride uses, ranked by count. Intentional repeat rides count; transport retries do not.
3. **MOCK - Peak and quiet hours (Colombo):** arrivals and ride uses shown separately for all 24 local hours.
4. **MOCK - Guest arrivals by tier:** checked-in guests grouped by package tier, not package sales.

The hourly chart is full width so its hour labels remain readable.

The dashboard covers all currently ingested mock visit dates. No date-range dashboard parameter is configured. Daily charts show individual dates; hourly charts sum across observed dates. For a particular date range, open a question, use Open Editor, add a WHERE visit_date condition before GROUP BY and save as a new question. Example:

```sql
SELECT visit_date, SUM(guest_arrivals) AS guest_arrivals
FROM reporting.mock_daily_arrivals
WHERE visit_date BETWEEN DATE '2026-10-16' AND DATE '2026-10-17'
GROUP BY visit_date ORDER BY visit_date;
```

Use your own demonstration dates. For zero-filled hourly activity, apply the same date condition to reporting.mock_daily_hour_grid.

**Metric interpretation matters:**

- A four-person package produces four guest arrivals only if all four guest tickets check in.
- A guest who uses three rides is one arrival and three ride uses.
- Unique guests in the ride reporting view means distinct guest entries/tickets for that attraction and date; it is not a cross-booking identity count.
- No check-out events exist, so arrivals cannot be used as current park occupancy.
- A zero hour means no recorded simulated activity. It does not prove the park was open or that an observation was complete.
- Dates without any observed events are not manufactured as zero-arrival dates.
- Ride popularity groups by stable attraction key; the chart uses the latest observed name. Renames do not split the same attraction into different rankings.

## 5. Read the Pipeline Health dashboard

Open Wonderland MOCK Pipeline Health:

- Totals and reconciliation shows mock arrivals, ride uses and rides whose arrival event has not arrived yet.
- Worker heartbeat and backlog shows the last poll time, heartbeat age in seconds, pending events and errors retained in the last batch.
- Healthy local operation normally has a recent heartbeat and zero backlog/errors.
- Refresh the dashboard to fetch current values. A displayed heartbeat age is the age when that query ran, not a continuously ticking timer.

Historical maximum delivery lag includes the initial backfill after the worker was stopped. It is not the current worker polling interval or the latency of your newest click.

Freshness uses real source recorded_at and Analytics received_at. The simulated visit occurred_at is used only for attendance/ride charts. A demonstration for yesterday can be recorded and delivered today without creating a false delivery-lag calculation.

## 6. Create your own mock activity and watch it arrive

1. Sign in to Wonderland with the existing administrator account.
2. Obtain a guest MOCK reference from a confirmed mock booking.
3. Open /admin/admission, paste the reference and choose Look up ticket.
4. Choose a simulation time inside its booked slot.
5. If not already checked in, click Simulate guest check-in.
6. Choose a ride and a later valid simulation time, then Record mock ride usage once.
7. Wait for the next worker poll (normally up to 5 seconds plus processing).
8. Reload the Operations dashboard. Arrivals/ride counts should change.
9. Open Pipeline Health: pending/errors should return to zero.
10. Repeat check-in to verify that the arrival count does not increase.

Keep transport retries on the same ride request/key. An intentional new ride submission is a separate usage fact.

During verification, guest 3 was checked in at simulated **16 October 2026, 10:00**, and River Rapids was recorded at 10:20. These actions were actually recorded on 17 October. Analytics delivery took **1.928 seconds** for the arrival and **2.781 seconds** for the ride in that measured run. This is one local measurement, not a production SLA.

After that run, the demo contains 3 guest arrivals and 3 ride uses: River Rapids 2, Wonder Quest 1. The 09:00 hour has 2 arrivals/2 rides and 10:00 has 1 arrival/1 ride.

## 7. Follow the delivery transaction

```text
Protected mock Admission action
  -> Admission transaction commits fact + outbox event
  -> restricted mock_analytics_feed view removes owner subject
  -> Python Analytics worker validates mock event
  -> Analytics transaction commits event hash + immutable fact
  -> separate source receipt acknowledges local delivery
  -> reporting aggregate views
  -> Metabase SELECT through metabase_reader
```

If the worker crashes after Analytics commits but before acknowledgement, the source event is delivered again. The same event ID/hash returns the existing result. A conflicting payload or duplicate guest identity is rejected rather than counted again.

There is no timestamp cursor that can skip a late-committing transaction: the feed selects events without a local receipt. Source acknowledgement is written only after target commit. Analytics ingestion order can differ from event order; rides awaiting an arrival are visible until the matching arrival arrives.

Malformed or conflicting events stay pending, errors are logged and the batch health records retained errors. This local worker retries; it does not implement an AWS DLQ/quarantine workflow. A sufficiently large set of permanently invalid events can block later batches; inspect and repair the producer/consumer deliberately rather than deleting receipts or overwriting immutable event content.

## 8. Check the database boundaries

| Role | Allowed access |
|---|---|
| analytics_source_dev | SELECT the sanitized Admission feed; INSERT local delivery receipts |
| analytics_dev | Own Analytics facts/reporting definitions; no operational Admission/Booking/Payment tables |
| metabase_reader | SELECT reporting aggregate views; default transactions read-only |
| metabase_app | Own the separate Metabase application database |

Operational owner IDs are removed at export. Reporting views do not expose guest names, emails, account subjects or guest ticket references. Analytics retains internal admission/ticket/event keys for duplicate safety; Metabase cannot read those base fact tables.

The local receipt column/table is independent of SNS publishing. Existing Admission outbox records are not falsely marked as AWS-published.

## 9. Code and migrations

| File | Purpose |
|---|---|
| services/admission/alembic/versions/0002_local_analytics.py | Sanitized feed and independent local acknowledgements |
| services/analytics/analytics_app/mock_pipeline.py | Validation, at-least-once delivery, duplicate detection and heartbeat |
| services/analytics/alembic/versions/0002_mock_facts.py | Immutable mock facts and reporting views |
| services/analytics/alembic/versions/0003_worker_health.py | Separate live worker-state table/view |
| deploy/local/postgres/007-reporting-roles.sql | Local restricted roles and separate Metabase database |
| deploy/local/reporting/privileges.sql | Named view/receipt permissions after migrations |
| analytics/metabase/sql/*.sql | Exact SQL for all six saved questions |
| analytics/metabase/dashboards.json | Dashboard/question names, local IDs and layout notes |
| scripts/start-analytics.ps1 | Complete local startup |
| tests/test_mock_analytics.py | Metrics, time zones, replay, crash recovery and reporting access |

Business mode defaults to disabled in the worker. Compose explicitly sets MOCK_ANALYTICS_ENABLED=true. The Analytics connection and restricted Admission feed connection are separate environment variables. The worker does not store Cognito access tokens or require AWS keys.

## 10. Recreate dashboards from source

Saved dashboards are persistent in wonderland_metabase. On a genuinely fresh Metabase application database:

1. Complete first-account setup and add the read-only connection.
2. Choose New -> SQL query and select Wonderland MOCK Reporting, not Sample Database.
3. Paste one file from analytics/metabase/sql.
4. Run it with Ctrl+Enter.
5. Choose Bar for the four operational charts or Table for the two health questions.
6. Save using the corresponding exact name in dashboards.json.
7. Create Wonderland MOCK Operations and add the four operational questions.
8. Create Wonderland MOCK Pipeline Health and add the two health questions.
9. Widen the hourly chart using its bottom-right resize handle. Save.
10. Reload both dashboards and confirm data, titles and the MOCK labels.

Questions must use the reporting views, never operational service tables. Existing SQL files use all observed dates. Save date-specific variants separately to preserve the supplied definitions.

## 11. Inspect health without Metabase

```powershell
docker compose logs --tail 30 analytics-mock
docker compose exec -T postgres psql -U analytics_dev -d wonderland -c "SELECT * FROM reporting.mock_worker_health;"
docker compose exec -T postgres psql -U metabase_reader -d wonderland -c "SELECT total_guest_arrivals,total_ride_uses,rides_awaiting_arrival FROM reporting.mock_pipeline_health;"
```

Logs identify event IDs and exception classes without printing payloads or database passwords.

To exercise restart recovery, stop only analytics-mock, create a new mock action, then start it again. Check that the backlog drains and the fact appears once. Do not delete source facts/receipts or the database volume to test recovery.

## 12. Verify

```powershell
Set-Location D:\Courses\Microservices
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Tests use wonderland_test. Development history and dashboards are preserved. Tests cover event ID/hash replay, aggregate uniqueness, out-of-order arrival/ride delivery, people versus package/ride counts, Asia/Colombo date conversion across UTC midnight, zero-filled hours, rejection of real/private/malformed payloads, commit-before-ack recovery and read-only reporting isolation, plus all previous features.

See [Step 08 validation](../evidence/step08-validation.md) for actual test results, browser evidence and measured delivery times.

## 13. Troubleshooting

| Symptom | Check |
|---|---|
| Docker pipe/engine unavailable | Start Docker Desktop and its Linux engine |
| Port 3000 not ready | Initial image download/migrations take time; inspect docker compose logs --tail 40 metabase |
| No charts after sign-in | Open the named dashboards in Our analytics, not the default example collection |
| Database connection refused | Metabase uses host postgres, port 5432 inside Docker |
| Permission denied on operational tables | Expected: use reporting views and metabase_reader |
| Empty charts | Confirm a mock guest was checked in; then check heartbeat/backlog |
| Old chart after new activity | Reload the dashboard; metadata sync is not the same as refreshing query results |
| Large historical lag | Old events were backfilled; check newest recorded/received times and live heartbeat separately |
| Retained errors / backlog | Inspect worker logs; fix invalid/conflicting events deliberately |
| Heartbeat grows | Worker is stopped or cannot reach source/target; inspect containers and DB access |
| Peak/quiet date seems wrong | Charts use simulated occurred_at in Asia/Colombo, not actual recorded_at |
| X-axis hours hidden | Widen the hourly dashboard card, then save |
| Lost Metabase password | Use its own local account recovery process; Cognito password is unrelated |

Stop Angular with Ctrl+C and use scripts/stop-local.ps1 to stop containers without deleting the volume. Back up the PostgreSQL data and Metabase application database before upgrades or destructive maintenance.

## 14. Remaining assignment work

This step is a local mock analytics milestone. It does not resolve Step 05's non-root AWS SSO setup or provision an Admission SNS/SQS pipeline. The existing Catalog/Booking AWS stack is unchanged. Admission delivery here is a working local database-outbox transport with independent acknowledgement, not a claim of cloud delivery.

Real payment integration, real attendance, financial reporting, cloud application hosting, EKS/API Gateway, hosted frontend and deployment evidence remain separate work. There is no revenue dashboard claiming that mock checkout collected money.

Next: Step 09 cloud feasibility and platform deployment preparation, while preserving these mock data boundaries.

Sources for Metabase setup: [official Docker guide](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker), [application database guide](https://www.metabase.com/docs/latest/installation-and-operation/configuring-application-database), [pinned release](https://github.com/metabase/metabase/releases/tag/v0.64.1).

