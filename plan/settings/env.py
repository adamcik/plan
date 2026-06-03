# This file is part of the plan timetable generator, see LICENSE for details.

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_parsed_env import Parsed, ParsedEnvSettings
from pydantic_settings import SettingsConfigDict


class Settings(ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    django_secret_key: SecretStr | None = Field(
        None, validation_alias="DJANGO_SECRET_KEY"
    )
    django_debug: bool = Field(False, validation_alias="DJANGO_DEBUG")
    django_debug_toolbar: bool = Field(False, validation_alias="DJANGO_DEBUG_TOOLBAR")
    django_allowed_hosts: Parsed[list[str]] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost"],
        validation_alias="DJANGO_ALLOWED_HOSTS",
    )
    django_csrf_trusted_origins: Parsed[list[str]] = Field(
        default_factory=list,
        validation_alias="DJANGO_CSRF_TRUSTED_ORIGINS",
    )
    django_use_x_forwarded_host: bool = Field(
        True, validation_alias="DJANGO_USE_X_FORWARDED_HOST"
    )
    django_secure_proxy_ssl_header: str | None = Field(
        None, validation_alias="DJANGO_SECURE_PROXY_SSL_HEADER"
    )
    django_log_level: str = Field("INFO", validation_alias="DJANGO_LOG_LEVEL")
    django_compress_enabled: bool = Field(
        True, validation_alias="DJANGO_COMPRESS_ENABLED"
    )
    django_compress_offline: bool = Field(
        True, validation_alias="DJANGO_COMPRESS_OFFLINE"
    )

    plan_base_dir: Path = Field(Path("/var/lib/plan"), validation_alias="PLAN_BASE_DIR")
    plan_cache_dir: Path = Field(
        Path("/var/cache/plan"), validation_alias="PLAN_CACHE_DIR"
    )
    plan_static_root: Path | None = Field(None, validation_alias="PLAN_STATIC_ROOT")
    plan_ical_cache_key_prefix: str = Field(
        "plan-ical", validation_alias="PLAN_ICAL_CACHE_KEY_PREFIX"
    )
    plan_scraper_cache_key_prefix: str = Field(
        "plan-scraper", validation_alias="PLAN_SCRAPER_CACHE_KEY_PREFIX"
    )

    pgdatabase: str = Field("plan", validation_alias="PGDATABASE")
    pguser: str = Field("plan", validation_alias="PGUSER")
    pgpassword: SecretStr = Field(SecretStr(""), validation_alias="PGPASSWORD")
    pghost: str = Field("127.0.0.1", validation_alias="PGHOST")
    pgport: str = Field("5432", validation_alias="PGPORT")
    pgconn_max_age: int = Field(0, validation_alias="PGCONN_MAX_AGE")

    memcached_location: str | None = Field(None, validation_alias="MEMCACHED_LOCATION")
    memcached_key_prefix: str = Field("plan", validation_alias="MEMCACHED_KEY_PREFIX")

    sentry_dsn: SecretStr | None = Field(None, validation_alias="SENTRY_DSN")
    sentry_environment: str = Field("production", validation_alias="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(
        0.001, validation_alias="SENTRY_TRACES_SAMPLE_RATE"
    )

    email_subject_prefix: str = Field("", validation_alias="EMAIL_SUBJECT_PREFIX")
    static_url: str = Field("/static/", validation_alias="STATIC_URL")
    timetable_institution: str | None = Field(
        None, validation_alias="TIMETABLE_INSTITUTION"
    )
    timetable_public_host: str | None = Field(
        None, validation_alias="TIMETABLE_PUBLIC_HOST"
    )
