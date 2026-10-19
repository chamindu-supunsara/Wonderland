# Analytics — Booking lifecycle and local mock BI

Owns the `analytics` and `reporting` schemas. The Step 05 worker retains its SQS Booking lifecycle projection. Step 08 adds a separate explicit mock worker: restricted Admission feed -> Analytics immutable facts/event hashes -> source receipt after commit. Reporting views feed persistent local Metabase dashboards without exposing operational identity fields.

Run `scripts/start-events.ps1 -Worker analytics` after non-root AWS authentication and the Analytics migration. Read [Step 05](../../docs/steps/05-events-sns-sqs.md) for the full guide. No HTTP API or public authentication bypass is added.

For the current local mock reporting lesson, run `scripts/start-analytics.ps1` and follow [Step 08](../../docs/steps/08-mock-analytics.md). No new Admission SNS/SQS infrastructure or real revenue reporting is claimed. The worker defaults to disabled unless MOCK_ANALYTICS_ENABLED=true is configured.
