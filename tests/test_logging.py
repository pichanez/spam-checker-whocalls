import logging
from phone_spam_checker.logging_config import JsonFormatter


def test_json_formatter():
    fmt = JsonFormatter()
    record = fmt.format(
        logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
    )
    assert record.startswith("{") and "hello" in record
