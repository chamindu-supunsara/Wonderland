"""Seed the next seven days; never reset an existing slot or hold."""

from datetime import datetime, time, timedelta

from sqlalchemy import select

from booking_app.db import session_factory
from booking_app.main import PARK_ZONE, create_slot, now
from booking_app.models import VisitSlot
from booking_app.schemas import SlotWrite


def seed():
    with session_factory().begin() as session:
        today = now().astimezone(PARK_ZONE).date()
        for day in range(1, 8):
            visit_date = today + timedelta(days=day)
            # Share the administrator's day lock to prevent overlapping seed/admin writes.
            from sqlalchemy import text

            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"slots:{visit_date}"},
            )
            for hour in (9, 12, 15):
                start = datetime.combine(visit_date, time(hour), PARK_ZONE)
                end = start + timedelta(hours=3)
                overlap = session.scalar(
                    select(VisitSlot.id).where(
                        VisitSlot.visit_date == visit_date,
                        VisitSlot.starts_at < end,
                        VisitSlot.ends_at > start,
                    )
                )
                if not overlap:
                    create_slot(
                        session,
                        SlotWrite(
                            visit_date=visit_date,
                            start_time=time(hour),
                            end_time=time(hour + 3),
                            capacity_guests=100,
                        ),
                    )


if __name__ == "__main__":
    seed()
