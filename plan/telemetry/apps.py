from django.apps import AppConfig


class TelemetryConfig(AppConfig):
    name = "plan.telemetry"

    def ready(self) -> None:
        # Settings-time initialization can make Django cache a partial settings
        # module. App readiness runs after settings load and covers commands too.
        from plan.telemetry import init

        init()
