"""Helper class to allow retrieval of log records after the fact."""

from __future__ import annotations

from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Handler, Logger, LogRecord
from typing import TYPE_CHECKING, Any

from wg_utilities.functions.datetime_helpers import utcnow

if TYPE_CHECKING:
    from collections.abc import Callable


class ListHandler(Handler):
    """Custom handler to allow retrieval of log records after the fact.

    Args:
        records_list (list): allows the user to pass in a pre-defined list to add records to
    """

    def __init__(
        self,
        records_list: list[Any] | None = None,
        *,
        log_ttl: int | None = 86400,
        on_record: Callable[[LogRecord], Any] | None = None,
        on_expiry: Callable[[LogRecord], Any] | None = None,
    ):
        super().__init__()

        # Can't use `or` here as `[]` is False
        self._records_list: list[LogRecord] = (
            records_list if records_list is not None else []
        )

        self.ttl = log_ttl
        self.on_record = on_record
        self.on_expiry = on_expiry

    def emit(self, record: LogRecord) -> None:
        """Add log record to the internal record store.

        Args:
            record (LogRecord): the new log record being "emitted"
        """
        self.expire_records()

        self._records_list.append(record)

        if self.on_record is not None:
            self.on_record(record)

    def expire_records(self) -> None:
        """Remove records older than `self.ttl`, and call `self.on_expiry` on them."""
        if self.ttl is None:
            return

        now = utcnow().timestamp()

        while self._records_list:
            record = self._records_list.pop(0)

            if record.created < (now - self.ttl):
                if self.on_expiry is not None:
                    self.on_expiry(record)
            else:
                self._records_list.insert(0, record)
                break

    @property
    def debug_records(self) -> list[LogRecord]:
        """Debug level records.

        Returns:
            list: a list of log records with the level DEBUG
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == DEBUG]

    @property
    def info_records(self) -> list[LogRecord]:
        """Info level records.

        Returns:
            list: a list of log records with the level INFO
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == INFO]

    @property
    def warning_records(self) -> list[LogRecord]:
        """Warning level records.

        Returns:
            list: a list of log records with the level WARNING
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == WARNING]

    @property
    def error_records(self) -> list[LogRecord]:
        """Error level records.

        Returns:
            list: a list of log records with the level ERROR
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == ERROR]

    @property
    def critical_records(self) -> list[LogRecord]:
        """Critical level records.

        Returns:
            list: a list of log records with the level CRITICAL
        """
        self.expire_records()
        return [record for record in self._records_list if record.levelno == CRITICAL]

    @property
    def records(self) -> list[LogRecord]:
        """All records.

        Returns:
            list: a list of log records with the level CRITICAL
        """
        self.expire_records()
        return self._records_list


def add_list_handler(
    logger: Logger,
    *,
    log_list: list[Any] | None = None,
    level: int = DEBUG,
    log_ttl: int | None = 86400,
    on_expiry: Callable[[LogRecord], Any] | None = None,
) -> ListHandler:
    """Add a ListHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        log_list (list): the list for the handler to write logs to
        level (int): the logging level to be used for the ListHandler
        log_ttl (int): number of seconds to retain a log for
        on_expiry (Callable): function to call with expired logs
    """

    l_handler = ListHandler(log_list, log_ttl=log_ttl, on_expiry=on_expiry)
    l_handler.setLevel(level)

    logger.addHandler(l_handler)

    return l_handler
