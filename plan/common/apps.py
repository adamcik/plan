from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "plan.common"

    def ready(self) -> None:
        # Settings are complete here, including for management commands.
        from plan.telemetry import init

        init()
