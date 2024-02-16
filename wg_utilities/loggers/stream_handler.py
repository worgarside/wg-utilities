"""Helper function to add a StreamHandler to a logger."""

from __future__ import annotations

from logging import DEBUG, Formatter, Logger, StreamHandler
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
