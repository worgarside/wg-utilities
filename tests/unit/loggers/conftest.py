"""Unit test fixtures for the loggers module."""
from __future__ import annotations

from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord, getLogger

from pytest import fixture

from tests.conftest import YieldFixture
from wg_utilities.loggers import ListHandler


@fixture(scope="function", name="list_handler")  # type: ignore[misc]
def _list_handler() -> ListHandler:
    """Fixture for creating a ListHandler instance."""
    l_handler = ListHandler(log_ttl=None)
    l_handler.setLevel(DEBUG)
    return l_handler


@fixture(scope="function", name="list_handler_prepopulated")  # type: ignore[misc]
def _list_handler_prepopulated(
    logger: Logger,
    list_handler: ListHandler,
    sample_log_record_messages_with_level: list[tuple[int, str]],
) -> ListHandler:
    """Fixture for creating a ListHandler instance with a pre-populated list."""
    logger.addHandler(list_handler)

    for level, message in sample_log_record_messages_with_level:
        logger.log(level, message)

    return list_handler


@fixture(scope="function", name="logger")  # type: ignore[misc]
def _logger() -> YieldFixture[Logger]:
    """Fixture for creating a logger."""

    _logger = getLogger("test_logger")
    _logger.setLevel(DEBUG)

    yield _logger

    _logger.handlers.clear()


@fixture(scope="function", name="sample_log_record")  # type: ignore[misc]
def _sample_log_record() -> LogRecord:
    """Fixture for creating a sample log record."""
    return LogRecord(
        name="test_logger",
        level=10,
        pathname=__file__,
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
        func=None,
    )


@fixture(  # type: ignore[misc]
    scope="function", name="sample_log_record_messages_with_level"
)
def _sample_log_record_messages_with_level() -> list[tuple[int, str]]:
    """Fixture for creating a list of sample log records."""
    log_levels = [DEBUG, INFO, WARNING, ERROR, CRITICAL] * 5

    return [
        (level, f"Test log message #{i} at level {level}")
        for i, level in enumerate(log_levels)
    ]
