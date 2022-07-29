"""Useful constants and functions for use in logging in other projects"""
from datetime import datetime
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    FileHandler,
    Formatter,
    Handler,
    Logger,
    LogRecord,
    StreamHandler,
)
from sys import stdout
from typing import Any, Callable, List, Optional

from wg_utilities.functions import force_mkdir

FORMATTER = Formatter(
    "%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s", "%Y-%m-%d %H:%M:%S"
)


class ListHandler(Handler):
    """Custom handler to allow retrieval of log records after the fact

    Args:
        records_list (list): allows the user to pass in a pre-defined list to add
         records to
    """

    def __init__(
        self,
        records_list: Optional[List[Any]] = None,
        *,
        log_ttl: Optional[int] = 86400,
        on_record: Optional[Callable[[LogRecord], Any]] = None,
        on_expiry: Optional[Callable[[LogRecord], Any]] = None,
    ):
        super().__init__()

        # Can't use `or` here as `[]` is False
        self._records_list: List[LogRecord] = (
            records_list if records_list is not None else []
        )

        self.ttl = log_ttl
        self.on_record = on_record
        self.on_expiry = on_expiry

    def emit(self, record: LogRecord) -> None:
        """ "Emit" the record by adding it to the internal record store

        Args:
            record (LogRecord): the new log record being "emitted"
        """
        self.expire_records()

        self._records_list.append(record)

        if self.on_record is not None:
            self.on_record(record)

    def expire_records(self) -> None:
        """Remove records older than `self.ttl`, and call `self.on_expiry` on them"""

        if self.ttl is None:
            return

        now = datetime.now().timestamp()

        while self._records_list:
            record = self._records_list.pop(0)

            if record.created < (now - self.ttl):
                if self.on_expiry is not None:
                    self.on_expiry(record)
            else:
                self._records_list.insert(0, record)
                break

    @property
    def debug_records(self) -> List[LogRecord]:
        """
        Returns:
            list: a list of log records with the level DEBUG
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == DEBUG]

    @property
    def info_records(self) -> List[LogRecord]:
        """
        Returns:
            list: a list of log records with the level INFO
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == INFO]

    @property
    def warning_records(self) -> List[LogRecord]:
        """
        Returns:
            list: a list of log records with the level WARNING
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == WARNING]

    @property
    def error_records(self) -> List[LogRecord]:
        """
        Returns:
            list: a list of log records with the level ERROR
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == ERROR]

    @property
    def critical_records(self) -> List[LogRecord]:
        """
        Returns:
            list: a list of log records with the level CRITICAL
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == CRITICAL]

    @property
    def records(self) -> List[LogRecord]:
        """
        Returns:
            list: a list of log records with the level CRITICAL
        """
        self.expire_records()
        return self._records_list


def create_file_handler(
    logfile_path: str, level: int = DEBUG, create_directory: bool = True
) -> FileHandler:
    """Create a file handler for use in other loggers

    Args:
        logfile_path (str): the path to the logging file
        level (int): the logging level to be used for the FileHandler
        create_directory (bool): whether to force-create the directory/ies the file is
         contained within

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
    logfile_path: str,
    level: int = DEBUG,
    create_directory: bool = True,
) -> None:
    """Add a FileHandler to an existing logger

    Args:
        logger (Logger): the logger to add a file handler to
        logfile_path (str): the path to the logging file
        level (int): the logging level to be used for the FileHandler
        create_directory (bool): whether to force-create the directory/ies the file is
         contained within
    """

    f_handler = create_file_handler(
        logfile_path, level, create_directory=create_directory
    )

    logger.addHandler(f_handler)


def add_list_handler(
    logger: Logger,
    *,
    log_list: Optional[List[Any]] = None,
    level: int = DEBUG,
    log_ttl: Optional[int] = 86400,
    on_expiry: Optional[Callable[[LogRecord], Any]] = None,
) -> ListHandler:
    """Add a ListHandler to an existing logger

    Args:
        logger (Logger): the logger to add a file handler to
        log_list (list): the list for the handler to write logs to
        level (int): the logging level to be used for the FileHandler
        log_ttl (int): number of seconds to retain a log for
        on_expiry (Callable): function to call with expired logs
    """

    l_handler = ListHandler(log_list, log_ttl=log_ttl, on_expiry=on_expiry)
    l_handler.setLevel(level)

    logger.addHandler(l_handler)

    return l_handler


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
