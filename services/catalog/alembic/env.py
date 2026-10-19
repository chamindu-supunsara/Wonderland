from contextlib import nullcontext

from alembic import context
from app.db import Base, get_engine
from app.models import Attraction, TicketPrice, TicketTier  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline():
    from app.config import get_settings

    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied = context.config.attributes.get("connection")
    with nullcontext(supplied) if supplied is not None else get_engine().connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_schemas=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
