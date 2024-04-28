"""Helper function to add a StreamHandler to a logger."""

from __future__ import annotations

from logging import DEBUG, Formatter, Logger, StreamHandler, getLogger
from sys import stdout
from time import gmtime

FORMATTER = Formatter(
    fmt="%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)
FORMATTER.converter = gmtime


def add_stream_handler(
    logger: Logger,
    *,
    formatter: Formatter | None = FORMATTER,
    level: int = DEBUG,
) -> Logger:
    """Add a FileHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        formatter (Formatter): the formatter to use in the stream logs
        level (int): the logging level to be used for the FileHandler

    Returns:
        Logger: the logger instance, returned for use in one-liners:
            `logger = add_stream_handler(logging.getLogger(__name__))`
    """

    s_handler = StreamHandler(stdout)
    s_handler.setFormatter(formatter)
    s_handler.setLevel(level)

    logger.addHandler(s_handler)

    return logger


def get_streaming_logger(
    name: str,
    *,
    formatter: Formatter | None = FORMATTER,
    level: int = DEBUG,
) -> Logger:
    """Get a logger with a StreamHandler attached.

    Args:
        name (str): the name of the logger to create
        formatter (Formatter): the formatter to use in the stream logs
        level (int): the logging level to be used for the FileHandler

    Returns:
        Logger: the logger instance, returned for use in one-liners:
            `logger = get_streaming_logger(__name__)`
    """
    logger = getLogger(name)
    logger.setLevel(level)

    return add_stream_handler(logger, formatter=formatter, level=level)


__all__ = ["FORMATTER", "add_stream_handler", "get_streaming_logger"]
