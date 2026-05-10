from django.db import connection
from django.test import SimpleTestCase


class TestDatabaseBackend(SimpleTestCase):
    def test_tests_run_on_postgresql(self):
        assert connection.vendor == "postgresql"
