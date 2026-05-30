import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, engine_from_config, pool

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL do ambiente tem prioridade sobre o alembic.ini. NÃO usamos
# set_main_option/get_section aqui: o ConfigParser do alembic faz interpolação
# de '%', então uma senha URL-encoded (ex.: %40 = '@') quebraria com
# "invalid interpolation syntax". Passamos a URL direto pro engine/contexto.
database_url = os.environ.get("DATABASE_URL")

from app.models import Base  # noqa: E402  (padrão do Alembic: após resolver a URL)

target_metadata = Base.metadata


def _resolve_url() -> str:
    return database_url or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if database_url:
        # URL vinda do ambiente: engine direto (sem ConfigParser).
        connectable = create_engine(database_url, poolclass=pool.NullPool, future=True)
    else:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
