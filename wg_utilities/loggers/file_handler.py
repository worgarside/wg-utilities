"""Helper functions for creating and adding FileHandlers to loggers."""

from __future__ import annotations

from logging import DEBUG, FileHandler, Formatter, Logger
from time import gmtime
from typing import TYPE_CHECKING

from wg_utilities.functions import force_mkdir

if TYPE_CHECKING:
    from pathlib import Path

FORMATTER = Formatter(
    fmt="%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)
FORMATTER.converter = gmtime


def create_file_handler(
    logfile_path: Path,
    level: int = DEBUG,
    *,
    create_directory: bool = True,
) -> FileHandler:
    """Create a file handler for use in other loggers.

    Args:
        logfile_path (str): the path to the logging file
        level (int): the logging level to be used for the FileHandler
        create_directory (bool): whether to force-create the directory/ies the file is contained within

    Returns:
        FileHandler: a log handler with a file as the output
    """
    if create_directory:
        force_mkdir(logfile_path, path_is_file=True)

    f_handler = FileHandler(logfile_path)
    f_handler.setFormatter(FORMATTER)
    f_handler.setLevel(level)

    return f_handler


def add_file_handler(
    logger: Logger,
    *,
    logfile_path: Path,
    level: int = DEBUG,
    create_directory: bool = True,
) -> Logger:
    """Add a FileHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        logfile_path (Path): the path to the logging file
        level (int): the logging level to be used for the FileHandler
        create_directory (bool): whether to force-create the directory/ies the file is contained within

    Returns:
        Logger: the logger instance, returned for use in one-liners:
            `logger = add_file_handler(logging.getLogger(__name__))`
    """

    f_handler = create_file_handler(
        logfile_path=logfile_path,
        level=level,
        create_directory=create_directory,
    )

    logger.addHandler(f_handler)

    return logger
