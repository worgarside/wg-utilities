"""Unit Tests for the `add_stream_handler` function."""

from __future__ import annotations

from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    NOTSET,
    WARNING,
    Formatter,
    Logger,
    StreamHandler,
)
from sys import stdout

import pytest

from wg_utilities.loggers.stream_handler import (
    FORMATTER,
    add_stream_handler,
    get_streaming_logger,
)


@pytest.mark.parametrize(
    "level",
    [
        CRITICAL,
        FATAL,
        ERROR,
        WARNING,
        INFO,
        DEBUG,
        NOTSET,
    ],
)
def test_log_level_is_set_correctly(level: int, logger: Logger) -> None:
    """Test that the log level is set correctly."""
    add_stream_handler(logger, level=level)

    assert len(logger.handlers) == 1

    s_handler = logger.handlers[0]

    assert isinstance(s_handler, StreamHandler)
    assert s_handler.level == level


@pytest.mark.parametrize(
    "formatter",
    [
        None,
        FORMATTER,
        Formatter(fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        Formatter(
            fmt="a stupid format really - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ),
    ],
)
def test_formatter_is_set_correctly(formatter: Formatter | None, logger: Logger) -> None:
    """Test that the formatter is set correctly."""
    add_stream_handler(logger, formatter=formatter)

    assert len(logger.handlers) == 1

    s_handler = logger.handlers[0]

    assert isinstance(s_handler, StreamHandler)
    assert s_handler.formatter is formatter


def test_handler_stream_is_stdout(logger: Logger) -> None:
    """Test that the stream is set to stdout."""
    add_stream_handler(logger)

    assert len(logger.handlers) == 1

    s_handler = logger.handlers[0]

    assert isinstance(s_handler, StreamHandler)
    assert s_handler.stream is stdout


def test_get_streaming_logger_instantiates_logger() -> None:
    """Test that `get_streaming_logger` instantiates a logger."""
    logger = get_streaming_logger(__name__)

    assert isinstance(logger, Logger)
    assert logger.name == __name__
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], StreamHandler)
    assert logger.handlers[0].stream is stdout
    assert logger.handlers[0].formatter is FORMATTER
    assert logger.handlers[0].level == DEBUG
