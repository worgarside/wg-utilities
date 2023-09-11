# pylint: disable=protected-access
"""Unit Tests for the `add_list_handler` function."""
from __future__ import annotations

from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    NOTSET,
    WARN,
    WARNING,
    Logger,
    LogRecord,
)

import pytest

from wg_utilities.loggers.list_handler import ListHandler, add_list_handler


def test_handler_is_applied_to_logger_correctly(logger: Logger) -> None:
    """Test that the handler is applied to the logger correctly."""

    add_list_handler(logger)

    assert len(logger.handlers) == 1

    l_handler = logger.handlers[0]

    assert isinstance(l_handler, ListHandler)
    assert l_handler._records_list == []
    assert l_handler.ttl == 86400
    assert l_handler.on_record is None
    assert l_handler.on_expiry is None


@pytest.mark.parametrize(
    "level",
    [
        CRITICAL,
        FATAL,
        ERROR,
        WARNING,
        WARN,
        INFO,
        DEBUG,
        NOTSET,
    ],
)
def test_log_level_is_set_correctly(level: int, logger: Logger) -> None:
    """Test that the log level is set correctly."""

    add_list_handler(logger, level=level)

    assert len(logger.handlers) == 1

    l_handler = logger.handlers[0]

    assert isinstance(l_handler, ListHandler)
    assert l_handler.level == level


def test_log_list_can_be_passed_in_then_used_without_accessing_from_handler(
    logger: Logger, sample_log_record_messages_with_level: list[tuple[int, str]]
) -> None:
    """Test the `log_list` parameter works as expected.

    Test that we can pass a list into `add_list_handler` and then reference it directly
    without needing to access the records from the handler itself
    """

    log_list: list[LogRecord] = []
    logged_messages = []

    add_list_handler(logger, log_list=log_list)

    for level, message in sample_log_record_messages_with_level:
        logger.log(level, message)
        logged_messages.append(message)

    assert len(log_list) == len(sample_log_record_messages_with_level)

    for log_record in log_list:
        logged_messages.remove(log_record.msg)

    assert len(logged_messages) == 0
