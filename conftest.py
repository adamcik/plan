"""Pytest fixtures shared by the Django test suite."""

from __future__ import annotations

import shutil

import pytest
from django.conf import settings
from django.db import connections
from django.test.utils import setup_databases, teardown_databases
from testing.postgresql import PostgresqlFactory


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Provision one temporary PostgreSQL server for the pytest session."""
    initdb = shutil.which("initdb")
    postgres = shutil.which("postgres")
    if initdb is None or postgres is None:
        raise RuntimeError("PostgreSQL binaries not found on PATH")

    postgresql = PostgresqlFactory(
        cache_initialized_db=True,
        initdb=initdb,
        postgres=postgres,
    )()
    dsn = postgresql.dsn()
    database_settings = {
        **settings.DATABASES["default"],
        "NAME": dsn["database"],
        "USER": dsn["user"],
        "PASSWORD": dsn.get("password", ""),
        "HOST": dsn["host"],
        "PORT": str(dsn["port"]),
    }
    settings.DATABASES["default"] = database_settings
    connections.databases["default"] = database_settings
    connection = connections["default"]
    connection.close()
    connection.settings_dict = database_settings

    with django_db_blocker.unblock():
        database_config = setup_databases(verbosity=0, interactive=False)

    try:
        yield
    finally:
        with django_db_blocker.unblock():
            teardown_databases(database_config, verbosity=0)
        postgresql.stop()
