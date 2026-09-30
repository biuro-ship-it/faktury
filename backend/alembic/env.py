from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import Baza

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Baza.metadata


def adres_bazy() -> str:
    # Kolejność: jawnie przekazany (testy) → `alembic -x url=...` → DATABASE_URL z .env.
    if url := config.attributes.get("url"):
        return url
    if url := context.get_x_argument(as_dictionary=True).get("url"):
        return url
    from app.config import ustawienia

    return ustawienia().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=adres_bazy(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    silnik = create_engine(adres_bazy(), poolclass=pool.NullPool)
    with silnik.connect() as polaczenie:
        context.configure(connection=polaczenie, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
