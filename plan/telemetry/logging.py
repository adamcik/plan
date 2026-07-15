"""Structured logging with active OpenTelemetry trace correlation."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict

from plan.telemetry.resources import log_attributes


def configure() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ExtraAdder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def add_otel_context(_: Any, __: str, event_dict: EventDict) -> EventDict:
    event_dict.update(log_attributes())
    return event_dict


class StructlogFormatter(structlog.stdlib.ProcessorFormatter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            *args,
            foreign_pre_chain=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
            ],
            processors=[
                add_otel_context,
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                *(
                    [structlog.dev.ConsoleRenderer(colors=True)]
                    if sys.stderr.isatty()
                    else [
                        structlog.processors.dict_tracebacks,
                        structlog.processors.JSONRenderer(),
                    ]
                ),
            ],
            **kwargs,
        )
