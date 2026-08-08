import json
import logging

from plan.telemetry.logging import StructlogFormatter


def test_structlog_formatter_includes_stdlib_extra_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="test event",
        args=(),
        exc_info=None,
    )
    record.schedule_created = True
    record.schedule_id = 123

    result = json.loads(StructlogFormatter().format(record))

    assert result["schedule_created"] is True
    assert result["schedule_id"] == 123
