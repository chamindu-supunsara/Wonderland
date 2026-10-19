from contextlib import nullcontext

from analytics_app.worker import Settings
from sqlalchemy import create_engine

from alembic import context

supplied = context.config.attributes.get("connection")
with (
    nullcontext(supplied)
    if supplied is not None
    else create_engine(Settings().database_url, connect_args={"connect_timeout": 5}).connect()
) as connection:
    context.configure(connection=connection, version_table_schema="analytics")
    with context.begin_transaction():
        context.run_migrations()
