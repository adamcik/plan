from datetime import date

from django.utils.safestring import mark_safe

from plan.settings.env import Settings
from plan.settings.runtime import _notice_html


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
