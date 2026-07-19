"""Structured logging tests."""

import json
import logging

from conductor.core.logging import JsonFormatter


def test_json_formatter_includes_safe_extra_fields() -> None:
    record = logging.LogRecord(
        name="conductor.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="job accepted",
        args=(),
        exc_info=None,
    )
    record.job_id = "job-123"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "job accepted"
    assert payload["job_id"] == "job-123"
    assert "timestamp" in payload
