from datetime import date
import os

from django.utils.safestring import mark_safe
from pydantic import ValidationError
import pytest

from plan.settings.env import Settings
from plan.settings.runtime import _notice_html


@pytest.mark.parametrize("field", ["django_secret_key", "pgpassword", "sentry_dsn"])
def test_secret_file_is_read_without_exporting_value(field, monkeypatch, tmp_path):
    variable = field.upper()
    monkeypatch.delenv(variable, raising=False)
    secret_file = tmp_path / "credential"
    secret_file.write_bytes(b" secret-with-spaces \r\n")
    monkeypatch.setenv(f"{variable}_FILE", str(secret_file))

    settings = Settings()

    assert getattr(settings, field).get_secret_value() == " secret-with-spaces "
    assert variable not in os.environ
    assert "secret-with-spaces" not in repr(settings)


@pytest.mark.parametrize("field", ["django_secret_key", "pgpassword", "sentry_dsn"])
def test_direct_secret_remains_supported(field, monkeypatch):
    variable = field.upper()
    monkeypatch.delenv(f"{variable}_FILE", raising=False)
    monkeypatch.setenv(variable, "direct-secret")

    assert getattr(Settings(), field).get_secret_value() == "direct-secret"


@pytest.mark.parametrize("field", ["django_secret_key", "pgpassword", "sentry_dsn"])
def test_secret_file_and_direct_value_are_mutually_exclusive(
    field, monkeypatch, tmp_path
):
    variable = field.upper()
    monkeypatch.setenv(variable, "never-print-this-secret")
    monkeypatch.setenv(f"{variable}_FILE", str(tmp_path / "unused"))

    with pytest.raises(ValidationError, match="not both") as error:
        Settings()

    assert "never-print-this-secret" not in str(error.value)


@pytest.mark.parametrize("contents", [None, b"", b"\n", b"\xffprivate-content"])
def test_invalid_secret_file_fails_closed(contents, monkeypatch, tmp_path):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    secret_file = tmp_path / "credential"
    if contents is not None:
        secret_file.write_bytes(contents)
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(secret_file))

    with pytest.raises(ValidationError, match="DJANGO_SECRET_KEY_FILE") as error:
        Settings()

    assert "private-content" not in str(error.value)


def test_notice_settings_parse_environment_overrides(monkeypatch, tmp_path):
    notice_file = tmp_path / "notice.html"
    notice_file.write_text("<p>Notice</p>", encoding="utf-8")
    monkeypatch.setenv("TIMETABLE_NOTICE_CUTOFF", "2026-08-24")
    monkeypatch.setenv("TIMETABLE_NOTICE_HTML_FILE", str(notice_file))

    settings = Settings()

    assert settings.timetable_notice_cutoff == date(2026, 8, 24)
    assert settings.timetable_notice_html_file == notice_file


def test_notice_html_loads_utf8_file(tmp_path):
    notice_file = tmp_path / "notice.html"
    notice_file.write_text("<p>Påminnelse</p>", encoding="utf-8")

    assert _notice_html(notice_file, default=mark_safe("")) == "<p>Påminnelse</p>"


def test_notice_html_uses_default_without_file():
    default = mark_safe("<p>Default</p>")

    assert _notice_html(None, default=default) is default
