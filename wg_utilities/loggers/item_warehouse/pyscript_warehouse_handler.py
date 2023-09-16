"""Custom handler to allow logging directly into an Item Warehouse."""

from __future__ import annotations

from asyncio import get_running_loop, run
from collections.abc import Callable
from http import HTTPStatus
from logging import DEBUG, Formatter, Logger, LogRecord, getLogger
from time import gmtime
from types import TracebackType
from typing import Any, Literal, Protocol, TypeVar

from requests import HTTPError

from .base_handler import BaseWarehouseHandler, WarehouseLog, WarehouseLogPage

FORMATTER = Formatter(
    fmt="%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)
FORMATTER.converter = gmtime


LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)


T = TypeVar("T")


class _PyscriptTaskExecutorProtocol(Protocol[T]):
    async def __call__(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        ...  # pragma: no cover


class HttpErrorHandler:
    def __enter__(self) -> HttpErrorHandler:
        return self

    def __exit__(
        self,
        _: type[type] | None,
        exc: Exception | None,
        __: TracebackType | None,
    ) -> bool:
        if exc and not (
            isinstance(exc, HTTPError)
            and exc.response.status_code == HTTPStatus.CONFLICT
        ):
            LOGGER.exception(
                "Error logging to Item Warehouse: %r",
                exc,
                exc_info=exc,
            )

        return True


http_error_handler = HttpErrorHandler


class PyscriptWarehouseHandler(BaseWarehouseHandler):
    """Custom handler to allow logging directly into an Item Warehouse from Pyscript.

    https://github.com/worgarside/addon-item-warehouse-api
    https://github.com/worgarside/addon-item-warehouse-website

    https://github.com/custom-components/pyscript

    The primary key of the log warehouse is a combination of:
        - log_hash (message content)
        - logger (name of the logger)
        - log_host (hostname of the machine the log was generated on)

    This means that the same log message from the same host will only be stored once.
    """

    def __init__(
        self,
        *,
        level: int | Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        warehouse_host: str | None = None,
        warehouse_port: int | None = None,
        pyscript_task_executor: _PyscriptTaskExecutorProtocol[
            WarehouseLog | WarehouseLogPage
        ],
    ) -> None:
        """Initialize the handler and Log Warehouse."""

        super().__init__(
            level=level,
            warehouse_host=warehouse_host,
            warehouse_port=warehouse_port,
        )

        self._pyscript_task_executor = pyscript_task_executor

    def emit(self, record: LogRecord) -> None:
        """Add log record to the internal record store.

        Args:
            record (LogRecord): the new log record being "emitted"
        """

        self._run_pyscript_task_executor(
            self.post_json_response,
            self.ITEM_ENDPOINT,
            timeout=5,
            json=self.get_log_payload(record),
        )

    async def _async_task_executor(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None:
        with http_error_handler():
            await self._pyscript_task_executor(func, *args, **kwargs)

    def _run_pyscript_task_executor(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None:
        try:
            loop = get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(self._async_task_executor(func, *args, **kwargs))
        else:
            run(self._async_task_executor(func, *args, **kwargs))


def add_pyscript_warehouse_handler(
    logger: Logger,
    *,
    level: int = DEBUG,
    warehouse_host: str | None = None,
    warehouse_port: int | None = None,
    pyscript_task_executor: _PyscriptTaskExecutorProtocol[
        WarehouseLog | WarehouseLogPage
    ],
) -> PyscriptWarehouseHandler:
    """Add a PyscriptWarehouseHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        level (int): the logging level to be used for the PyscriptWarehouseHandler
        warehouse_host (str): the hostname of the Item Warehouse
        warehouse_port (int): the port of the Item Warehouse
        pyscript_task_executor (Callable): the Pyscript task executor (if applicable)

    Returns:
        PyscriptWarehouseHandler: the PyscriptWarehouseHandler that was added to the logger
    """

    wh_handler = PyscriptWarehouseHandler(
        level=level,
        warehouse_host=warehouse_host,
        warehouse_port=warehouse_port,
        pyscript_task_executor=pyscript_task_executor,
    )

    for handler in logger.handlers:
        if isinstance(
            handler, PyscriptWarehouseHandler
        ) and handler.base_url == PyscriptWarehouseHandler.get_base_url(
            warehouse_host, warehouse_port
        ):
            LOGGER.warning(
                "PyscriptWarehouseHandler already exists for %s", handler.base_url
            )
            return handler

    logger.addHandler(wh_handler)
    return wh_handler


__all__ = ["PyscriptWarehouseHandler", "add_pyscript_warehouse_handler"]
