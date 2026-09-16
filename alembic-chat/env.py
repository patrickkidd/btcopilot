"""The chat app's chain. Its database is its own and starts empty (R-0322), so
this env knows only the chat app's tables and refuses to touch anything else.

The url comes from FLASK_SQLALCHEMY_DATABASE_URI, the same name the app reads,
so a chain run and an app start cannot point at different databases by accident.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from btcopilot.chattables import TABLES, metadata

config = context.config
# run from the ini on a checkout, or from `flask admin db` on an installed box
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = metadata()


def url() -> str:
    uri = config.get_main_option("sqlalchemy.url") or os.getenv(
        "FLASK_SQLALCHEMY_DATABASE_URI"
    )
    if not uri:
        raise RuntimeError(
            "FLASK_SQLALCHEMY_DATABASE_URI must name the chat app's own database"
        )
    return uri


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in TABLES
    return True


def run_offline():
    context.configure(
        url=url(),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online():
    section = config.get_section(config.config_ini_section)
    section["sqlalchemy.url"] = url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
