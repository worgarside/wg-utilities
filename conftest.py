"""Pytest config file, used for creating fixtures etc."""

from __future__ import annotations

from collections.abc import Generator
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord, getLogger
from pathlib import Path
from typing import Callable, TypeVar

from pytest import fixture
from requests import get
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import MissingSchema

from wg_utilities.loggers import ListHandler

T = TypeVar("T")
YieldFixture = Generator[T, None, None]

EXCEPTION_GENERATORS: list[
    tuple[
        type[Exception],
        Callable[..., object],
        tuple[object, ...],
    ]
] = [
    (AttributeError, lambda arg1: arg1.keys(), ([1, 2, 3],)),
    (
        RequestsConnectionError,
        get,
        ("http://www.not-a-real-website-abc.com",),
    ),
    (FileNotFoundError, open, ("nonexistent_file.txt", "r")),
    (IsADirectoryError, open, (Path(__file__).parent, "r")),
    (IndexError, lambda arg1: arg1[10], ([1, 2, 3],)),
    (KeyError, lambda arg1: arg1["missing"], ({"key": "value"},)),
    (LookupError, lambda arg1: arg1["missing"], ({"key": "value"},)),
    (MissingSchema, get, ("completely invalid",)),
    # pylint: disable=undefined-variable
    (NameError, lambda: dog, ()),  # type: ignore[name-defined]  # noqa: F821
    (TypeError, lambda arg1, arg2: arg1 + arg2, ("string", 10)),
    (UnicodeError, lambda arg1: arg1.encode("ascii"), ("\u2013",)),
    (UnicodeEncodeError, lambda arg1: arg1.encode("ascii"), ("\u2013",)),
    (ValueError, int, ("string",)),
    (ZeroDivisionError, lambda: 1 / 0, ()),
]


@fixture(scope="function", name="list_handler")  # type: ignore[misc]
def _list_handler() -> ListHandler:
    """Fixture for creating a ListHandler instance."""
    l_handler = ListHandler(log_ttl=None)
    l_handler.setLevel(DEBUG)
    return l_handler


@fixture(scope="function")  # type: ignore[misc]
def list_handler_prepopulated(
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


@fixture(scope="function")  # type: ignore[misc]
def sample_log_record() -> LogRecord:
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
