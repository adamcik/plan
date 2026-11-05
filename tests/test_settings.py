from datetime import date
import os

from django.utils.safestring import mark_safe
from pydantic_settings import SettingsError
import pytest

from plan.settings.env import Settings
from plan.settings.runtime import _notice_html


@pytest.mark.parametrize("field", ["django_secret_key", "pgpassword", "sentry_dsn"])
def test_secret_file_is_read_without_exporting_value(field, monkeypatch, tmp_path):
    variable = field.upper()
    monkeypatch.delenv(variable, raising=False)
    secret_file = tmp_path / variable
    secret_file.write_bytes(b" secret-with-spaces \r\n")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))

    settings = Settings()

    assert getattr(settings, field).get_secret_value() == "secret-with-spaces"
    assert variable not in os.environ
    assert "secret-with-spaces" not in repr(settings)


@pytest.mark.parametrize("field", ["django_secret_key", "pgpassword", "sentry_dsn"])
def test_direct_secret_remains_supported(field, monkeypatch):
    variable = field.upper()
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    monkeypatch.setenv(variable, "direct-secret")

    assert getattr(Settings(), field).get_secret_value() == "direct-secret"


@pytest.mark.parametrize("field", ["django_secret_key", "pgpassword", "sentry_dsn"])
def test_environment_value_takes_precedence_over_credential(
    field, monkeypatch, tmp_path
):
    variable = field.upper()
    (tmp_path / variable).write_text("credential-secret", encoding="utf-8")
    monkeypatch.setenv(variable, "environment-secret")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))

    assert getattr(Settings(), field).get_secret_value() == "environment-secret"


def test_invalid_credential_fails_without_exposing_contents(monkeypatch, tmp_path):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    (tmp_path / "DJANGO_SECRET_KEY").write_bytes(b"\xffprivate-content")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))

    with pytest.raises(SettingsError) as error:
        Settings()

    assert "private-content" not in str(error.value)


def test_credentials_preserve_parsed_environment_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    (tmp_path / "DJANGO_SECRET_KEY").write_text("credential-secret", encoding="utf-8")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "alpha.example,beta.example")

    settings = Settings()

    assert settings.django_secret_key.get_secret_value() == "credential-secret"
    assert settings.django_allowed_hosts == ["alpha.example", "beta.example"]


def test_explicit_secrets_directory_remains_supported_without_systemd(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    (tmp_path / "DJANGO_SECRET_KEY").write_text("credential-secret", encoding="utf-8")

    assert (
        Settings(_secrets_dir=tmp_path).django_secret_key.get_secret_value()
        == "credential-secret"
    )


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
