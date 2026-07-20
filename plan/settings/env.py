# This file is part of the plan timetable generator, see LICENSE for details.

from importlib.metadata import PackageNotFoundError, metadata, version
import os
from pathlib import Path
import socket
from enum import StrEnum

from pydantic import Field, SecretStr, model_validator
from pydantic_parsed_env import Parsed, ParsedEnvSettings
from pydantic_settings import SettingsConfigDict

from plan.telemetry.resources import _uwsgi_worker_id


class TelemetryComponent(StrEnum):
    TRACING = "tracing"
    METRICS = "metrics"


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
    plan_scraper_cache_key_prefix: str = Field(
        "plan-scraper", validation_alias="PLAN_SCRAPER_CACHE_KEY_PREFIX"
    )
    timetable_ical_cache_duration_seconds: int = Field(
        30 * 24 * 60 * 60,
        validation_alias="TIMETABLE_ICAL_CACHE_DURATION_SECONDS",
    )
    timetable_schedule_cache_duration_seconds: int | None = Field(
        None,
        validation_alias="TIMETABLE_SCHEDULE_CACHE_DURATION_SECONDS",
    )
    timetable_snapshot_cache_default_ttl: int = Field(
        3 * 24 * 60 * 60,
        validation_alias="TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL",
    )
    timetable_snapshot_cache_disk_ttl: int | None = Field(
        None,
        validation_alias="TIMETABLE_SNAPSHOT_CACHE_DISK_TTL",
    )
    timetable_semester_freshness_cache_default_ttl: int = Field(
        3 * 24 * 60 * 60,
        validation_alias="TIMETABLE_SEMESTER_FRESHNESS_CACHE_DEFAULT_TTL",
    )
    timetable_location_cache_ttl: int = Field(
        24 * 60 * 60,
        validation_alias="TIMETABLE_LOCATION_CACHE_TTL",
    )
    timetable_schedule_data_cache_ttl: int = Field(
        60 * 60,
        validation_alias="TIMETABLE_SCHEDULE_DATA_CACHE_TTL",
    )
    timetable_course_stats_cache_ttl: int = Field(
        5 * 60,
        validation_alias="TIMETABLE_COURSE_STATS_CACHE_TTL",
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
    sentry_release: str = Field(
        default_factory=lambda: f"plan@{_current_package_version()}",
        validation_alias="SENTRY_RELEASE",
    )
    sentry_traces_sample_rate: float = Field(
        0.001, validation_alias="SENTRY_TRACES_SAMPLE_RATE"
    )
    sentry_enable_logs: bool = Field(False, validation_alias="SENTRY_ENABLE_LOGS")
    plan_telemetry_components: Parsed[set[TelemetryComponent]] = Field(
        default_factory=set, validation_alias="PLAN_TELEMETRY_COMPONENTS"
    )
    otel_exporter_otlp_endpoint: str = Field(
        "http://127.0.0.1:4318", validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field("plan", validation_alias="OTEL_SERVICE_NAME")
    otel_service_version: str = Field(
        default_factory=lambda: _current_package_version(),
        validation_alias="OTEL_SERVICE_VERSION",
    )
    otel_deployment_environment: str = Field(
        "production", validation_alias="OTEL_DEPLOYMENT_ENVIRONMENT"
    )
    otel_service_instance_id: str | None = Field(
        None, validation_alias="OTEL_SERVICE_INSTANCE_ID"
    )
    otel_vcs_revision: str | None = Field(None, validation_alias="OTEL_VCS_REVISION")
    otel_trace_sample_rate: float = Field(
        0.1, validation_alias="OTEL_TRACE_SAMPLE_RATE"
    )
    otel_path_trace_sample_rates: dict[str, float] = Field(
        default_factory=lambda: {
            r"^/[^/]+/[^/]+/ical(/|$)": 0.01,
        },
        validation_alias="OTEL_PATH_TRACE_SAMPLE_RATES",
    )
    otel_export_timeout_seconds: float = Field(
        10, validation_alias="OTEL_EXPORT_TIMEOUT_SECONDS"
    )
    otel_metric_export_interval_seconds: float = Field(
        60, validation_alias="OTEL_METRIC_EXPORT_INTERVAL_SECONDS"
    )
    timetable_report_uri: str | None = Field(
        None, validation_alias="TIMETABLE_REPORT_URI"
    )

    email_subject_prefix: str = Field("", validation_alias="EMAIL_SUBJECT_PREFIX")
    static_url: str = Field("/static/", validation_alias="STATIC_URL")
    timetable_institution: str | None = Field(
        None, validation_alias="TIMETABLE_INSTITUTION"
    )
    timetable_public_host: str | None = Field(
        None, validation_alias="TIMETABLE_PUBLIC_HOST"
    )

    @model_validator(mode="after")
    def default_telemetry_resource_labels(self) -> "Settings":
        if self.otel_vcs_revision is None:
            self.otel_vcs_revision = _current_package_revision()
        return self

    @property
    def otel_resource_attributes(self) -> dict[str, str | int]:
        attributes: dict[str, str | int] = {
            "service.name": self.otel_service_name,
            "service.version": self.otel_service_version,
            "deployment.environment.name": self.otel_deployment_environment,
            "service.instance.id": self.otel_service_instance_id
            or _default_service_instance_id(self.otel_deployment_environment),
            "process.pid": os.getpid(),
        }
        if self.otel_vcs_revision:
            attributes["vcs.revision"] = self.otel_vcs_revision
        return attributes


def _default_service_instance_id(deployment_environment: str) -> str:
    parts = [socket.gethostname(), deployment_environment]
    if (worker_id := _uwsgi_worker_id()) is not None:
        parts.append(str(worker_id))
    return "-".join(parts)


def _current_package_version() -> str:
    try:
        return version("plan")
    except PackageNotFoundError:
        return "unknown"


def _current_package_revision() -> str | None:
    try:
        package_metadata = metadata("plan")
    except PackageNotFoundError:
        return None
    return package_metadata.get("Vcs-Revision")
