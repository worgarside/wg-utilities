"""Useful constants and functions for use in logging in other projects"""

from logging import DEBUG, FileHandler, Formatter, Logger, StreamHandler
from sys import stdout

FORMATTER = Formatter(
    "%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s", "%Y-%m-%d %H:%M:%S"
)


def create_file_handler(logfile_path: str, level: int = DEBUG) -> FileHandler:
    """Create a file handler for use in other loggers

    Args:
        logfile_path (str): the path to the logging file
        level (int): the logging level to be used for the FileHandler

    Returns:
        FileHandler: a log handler with a file as the output
    """

    f_handler = FileHandler(logfile_path)
    f_handler.setFormatter(FORMATTER)
    f_handler.setLevel(level)

    return f_handler


def add_file_handler(logger: Logger, *, logfile_path: str, level: int = DEBUG) -> None:
    """Add a FileHandler to an existing logger

    Args:
        logger (Logger): the logger to add a file handler to
        logfile_path (str): the path to the logging file
        level (int): the logging level to be used for the FileHandler
    """

    f_handler = create_file_handler(logfile_path, level)

    logger.addHandler(f_handler)


def add_stream_handler(
    logger: Logger, *, formatter: Formatter = FORMATTER, level: int = DEBUG
) -> None:
    """Add a FileHandler to an existing logger

    Args:
        logger (Logger): the logger to add a file handler to
        formatter (Formatter): the formatter to use in the stream logs
        level (int): the logging level to be used for the FileHandler
    """

    s_handler = StreamHandler(stdout)
    s_handler.setFormatter(formatter)
    s_handler.setLevel(level)

    logger.addHandler(s_handler)
