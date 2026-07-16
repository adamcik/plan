from django.db import connection


def test_tests_run_on_postgresql():
    assert connection.vendor == "postgresql"
