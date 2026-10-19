from contextlib import nullcontext

from alembic import context
from booking_app.db import Base, get_engine
from booking_app.models import Booking, OutboxEvent, VisitSlot  # noqa: F401

supplied = context.config.attributes.get("connection")
with nullcontext(supplied) if supplied is not None else get_engine().connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table_schema="booking",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()
