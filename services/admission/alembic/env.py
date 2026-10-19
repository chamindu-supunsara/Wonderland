from contextlib import nullcontext

from admission_app.db import get_engine
from admission_app.models import Ticket  # noqa: F401

from alembic import context

supplied = context.config.attributes.get("connection")
with nullcontext(supplied) if supplied is not None else get_engine().connect() as connection:
    context.configure(connection=connection, version_table_schema="admission")
    with context.begin_transaction():
        context.run_migrations()
