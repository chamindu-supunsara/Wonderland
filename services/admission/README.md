# MOCK Admission service

FastAPI on port 8004 with its own PostgreSQL role/schema and Docker image. Existing Cognito administrators can look up confirmed mock guest tickets, simulate one check-in per ticket and record ride usage. Booking owns ticket validity; Admission validates its protected HTTP snapshot and stores an independent local projection. New rides require check-in and an active Catalog attraction. Visitor history is filtered by booking owner.

MOCK_ADMISSION_ENABLED defaults to false; local Compose explicitly enables it. Simulation timestamps must be inside the booked slot and ride times must follow check-in. Actual audit times are retained separately. Ride submissions use a stable UUID retry key and request hash. Facts and MockGuestCheckedIn / MockRideUsed outbox events commit together. Admission events are stored locally; no SNS publisher or BI integration is implemented for this new source yet.

See [the complete Step 07 walkthrough](../../docs/steps/07-mock-admission.md) and [validation](../../docs/evidence/step07-validation.md). This implementation grants no real park admission.

