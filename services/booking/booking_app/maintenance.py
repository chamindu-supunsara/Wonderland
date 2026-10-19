"""Pre-payment development hold expiry. Provider reconciliation is required before Step 06."""

import time

from wonderland_events.health import heartbeat

from booking_app.db import session_factory
from booking_app.main import expire_holds

if __name__ == "__main__":
    while True:
        with session_factory().begin() as session:
            expire_holds(session)
        heartbeat()
        time.sleep(15)
