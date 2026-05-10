"""Django test runner that provisions ephemeral PostgreSQL."""

from __future__ import annotations

import shutil

from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner
from testing.postgresql import Postgresql
from testing.postgresql import PostgresqlFactory


class PostgresTestRunner(DiscoverRunner):
    """Run Django tests against a temporary PostgreSQL instance."""

    _factory: PostgresqlFactory | None = None

    _postgresql: Postgresql | None = None

    def setup_databases(self, **kwargs):
        if self._factory is None:
            initdb = shutil.which("initdb")
            postgres = shutil.which("postgres")
            if initdb is None or postgres is None:
                raise RuntimeError("PostgreSQL binaries not found on PATH")
            self._factory = PostgresqlFactory(
                cache_initialized_db=True,
                initdb=initdb,
                postgres=postgres,
            )
        self._postgresql = self._factory()
        dsn = self._postgresql.dsn()
        base_settings = dict(settings.DATABASES.get("default", {}))
        database_settings = {
            **base_settings,
            "ENGINE": "django.db.backends.postgresql",
            "NAME": dsn["database"],
            "USER": dsn["user"],
            "PASSWORD": dsn.get("password", ""),
            "HOST": dsn["host"],
            "PORT": str(dsn["port"]),
        }
        settings.DATABASES["default"] = database_settings
        connections.databases["default"] = database_settings
        if "default" in connections:
            connection = connections["default"]
            connection.close()
            connection.settings_dict = database_settings
        return super().setup_databases(**kwargs)

    def teardown_databases(self, old_config, **kwargs):
        try:
            return super().teardown_databases(old_config, **kwargs)
        finally:
            if self._postgresql is not None:
                self._postgresql.stop()
                self._postgresql = None
