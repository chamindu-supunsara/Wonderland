# Local MOCK Payment service

FastAPI on port 8003 with its own PostgreSQL schema/role. Cognito authenticates the owner. Totals come from Booking. An immutable simulated outcome is committed before settlement; retry the same checkout/outcome after an unknown response. Explicit MOCK_PAYMENTS_ENABLED=true is required in both services; local Compose enables it.

Booking owns atomic capacity, settlement receipts, demonstration guest tickets and mock outbox events. No card data, real charge, refund or valid admission credential is involved. Provider integration remains future work. See [the full Step 06 guide](../../docs/steps/06-mock-payment.md).

