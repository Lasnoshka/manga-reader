import json
import logging

from app.core.logger import JsonFormatter, request_id_var


def _record(message: str, **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_required_fields():
    formatter = JsonFormatter()
    payload = json.loads(formatter.format(_record("hello")))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "hello"
    assert "ts" in payload and payload["ts"].endswith("Z")
    assert "file" in payload


def test_json_formatter_includes_request_id_when_set():
    formatter = JsonFormatter()
    token = request_id_var.set("rid-xyz")
    try:
        payload = json.loads(formatter.format(_record("hi")))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "rid-xyz"


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    payload = json.loads(formatter.format(_record("done", duration_ms=12.5, status=200)))
    assert payload["duration_ms"] == 12.5
    assert payload["status"] == 200


def test_json_formatter_serializes_unjsonable_extra_via_repr():
    formatter = JsonFormatter()
    obj = object()
    payload = json.loads(formatter.format(_record("weird", weird=obj)))
    assert payload["weird"] == repr(obj)
