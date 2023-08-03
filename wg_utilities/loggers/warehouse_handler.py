"""Custom handler to allow logging directly into an Item Warehouse."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from hashlib import md5
from http import HTTPStatus
from json import JSONDecodeError, dumps
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Formatter,
    Handler,
    Logger,
    LogRecord,
    getLogger,
)
from os import getenv
from socket import gethostname
from time import gmtime
from traceback import format_exception
from typing import Any, Final, Literal, Protocol, TypedDict, TypeVar, cast

from requests import HTTPError
from requests.exceptions import RequestException

from wg_utilities.clients.json_api_client import JsonApiClient, StrBytIntFlt
from wg_utilities.loggers.stream_handler import add_stream_handler

FORMATTER = Formatter(
    fmt="%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)
FORMATTER.converter = gmtime


LOGGER = getLogger(__name__)
LOGGER.setLevel(ERROR)
add_stream_handler(LOGGER)


class WarehouseLogPage(TypedDict):
    """Type for a page of log records."""

    count: int
    items: list[WarehouseLog]
    next_offset: int | None
    total: int


class WarehouseLog(TypedDict):
    """Type for a log record."""

    created_at: str
    file: str
    level: int
    line: int
    log_hash: str
    log_host: str
    logger: str
    message: str
    module: str
    process: str
    thread: str


T = TypeVar("T")


class _PyscriptTaskExecutorProtocol(Protocol[T]):
    def __call__(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        ...  # pragma: no cover


class WarehouseHandler(Handler, JsonApiClient[WarehouseLog | WarehouseLogPage]):
    """Custom handler to allow logging directly into an Item Warehouse.

    https://github.com/worgarside/addon-item-warehouse

    The primary key of the log warehouse is a combination of:
        - log_hash (message content)
        - logger (name of the logger)
        - log_host (hostname of the machine the log was generated on)

    This means that the same log message from the same host will only be stored once.
    """

    HOST_NAME = gethostname()

    ITEM_NAME: Final = "log"
    WAREHOUSE_NAME: Final = "lumberyard"

    WAREHOUSE_ENDPOINT: Final = "/warehouses/lumberyard"

    _WAREHOUSE_SCHEMA = {
        "name": WAREHOUSE_NAME,
        "item_name": ITEM_NAME,
        "item_schema": {
            "created_at": {"nullable": False, "type": "float"},
            "exception_message": {
                "nullable": True,
                "type": "string",
                "type_kwargs": {"length": 2048},
            },
            "exception_type": {
                "nullable": True,
                "type": "string",
                "type_kwargs": {"length": 64},
            },
            "exception_traceback": {
                "nullable": True,
                "type": "string",
                "type_kwargs": {"length": 2048},
            },
            "file": {
                "nullable": False,
                "type": "string",
                "type_kwargs": {"length": 255},
            },
            "level": {"nullable": False, "type": "integer"},
            "line": {"nullable": False, "type": "integer"},
            "log_hash": {
                "nullable": False,
                "primary_key": True,
                "type": "string",
                "type_kwargs": {"length": 32},
            },
            "log_host": {
                "default": "func:client_ip",
                "nullable": False,
                "primary_key": True,
                "type": "string",
                "type_kwargs": {"length": 45},
            },
            "logger": {
                "nullable": False,
                "primary_key": True,
                "type": "string",
                "type_kwargs": {"length": 255},
            },
            "message": {
                "nullable": False,
                "type": "string",
                "type_kwargs": {"length": 2048},
            },
            "module": {
                "nullable": False,
                "type": "string",
                "type_kwargs": {"length": 255},
            },
            "process": {
                "nullable": False,
                "type": "string",
                "type_kwargs": {"length": 255},
            },
            "thread": {
                "nullable": False,
                "type": "string",
                "type_kwargs": {"length": 255},
            },
        },
    }

    def __init__(
        self,
        *,
        level: int | Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        warehouse_host: str | None = None,
        warehouse_port: int | None = None,
        allow_connection_errors: bool = False,
        pyscript_task_executor: _PyscriptTaskExecutorProtocol[
            WarehouseLog | WarehouseLogPage
        ]
        | None = None,
    ) -> None:
        """Initialize the handler and Log Warehouse."""

        Handler.__init__(self, level=level)

        warehouse_host = warehouse_host or str(
            getenv("ITEM_WAREHOUSE_HOST", "http://homeassistant.local")
        )
        warehouse_port = warehouse_port or int(getenv("ITEM_WAREHOUSE_PORT", "0"))

        base_url = warehouse_host
        if warehouse_port:
            base_url += f":{warehouse_port}"
        base_url += "/v1"

        JsonApiClient.__init__(self, base_url=base_url)

        self._allow_connection_errors = allow_connection_errors
        self._pyscript_task_executor = pyscript_task_executor

        self._initialize_warehouse()

    def _initialize_warehouse(self) -> None:
        schema: WarehouseLog
        try:
            schema = self.get_json_response(  # type: ignore[assignment]
                self.WAREHOUSE_ENDPOINT, timeout=5
            )
        except HTTPError as exc:
            if exc.response.status_code == HTTPStatus.NOT_FOUND:
                schema = self.post_json_response(  # type: ignore[assignment]
                    "/warehouses", json=self._WAREHOUSE_SCHEMA, timeout=5
                )
                LOGGER.info("Created new Warehouse: %r", schema)
        except (
            ConnectionError,
            RequestException,
        ) as exc:
            LOGGER.exception("Error creating Warehouse: %r", exc)

            if not self._allow_connection_errors:
                raise
        else:
            LOGGER.info(
                "Warehouse already exists - created at %s",
                schema.pop("created_at", None),  # type: ignore[misc]
            )
            if schema != self._WAREHOUSE_SCHEMA:  # type: ignore[comparison-overlap]
                raise ValueError(
                    "Warehouse schema does not match expected schema: "
                    + dumps(schema, default=repr)
                )

    def emit(self, record: LogRecord) -> None:
        """Add log record to the internal record store.

        Args:
            record (LogRecord): the new log record being "emitted"
        """

        log_payload = {
            "created_at": record.created,
            "file": record.pathname,
            "level": record.levelno,
            "line": record.lineno,
            "log_hash": self._get_log_hash(record),
            "log_host": self.HOST_NAME,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "process": record.processName,
            "thread": record.threadName,
        }

        if record.exc_info and record.exc_info[0]:
            log_payload["exception_message"] = str(record.exc_info[1])
            log_payload["exception_type"] = record.exc_info[0].__name__
            log_payload["exception_traceback"] = "".join(
                format_exception(record.exc_info[1])
            )

        try:
            self.post_json_response(
                f"{self.WAREHOUSE_ENDPOINT}/items",
                json=log_payload,
            )
        except HTTPError as exc:
            error_detail = exc.response.text
            try:
                if (error_detail := exc.response.json()).get("detail", {}).get(
                    "type"
                ) == "ItemExistsError":
                    return
            except (AttributeError, LookupError, JSONDecodeError):
                pass

            LOGGER.error(
                "Error posting log to Warehouse: %i %s; %r",
                exc.response.status_code,
                exc.response.reason,
                error_detail,
            )
        except (
            ConnectionError,
            RequestException,
        ) as exc:
            LOGGER.error("Error posting log to Warehouse: %r", exc)

            if not self._allow_connection_errors:
                raise
        except Exception as exc:  # pylint: disable=broad-except # pragma: no cover
            LOGGER.error(repr(exc))

    def get_json_response(
        self,
        url: str,
        /,
        *,
        params: dict[StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | None = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> WarehouseLog | WarehouseLogPage:
        """Get a JSON response from the warehouse.

        This is overridden to allow compatibility with Pyscript.
        https://hacs-pyscript.readthedocs.io/en/latest/reference.html#task-executor
        """
        if self._pyscript_task_executor is not None:
            return self._pyscript_task_executor(
                super().get_json_response,
                url,
                params=params,
                header_overrides=header_overrides,
                timeout=timeout,
                json=json,
                data=data,
            )

        return super().get_json_response(
            url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )

    def post_json_response(
        self,
        url: str,
        /,
        *,
        params: dict[StrBytIntFlt, StrBytIntFlt | Iterable[StrBytIntFlt] | None]
        | None = None,
        header_overrides: Mapping[str, str | bytes] | None = None,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> WarehouseLog | WarehouseLogPage:
        """Post a JSON response to the warehouse.

        This is overridden to allow compatibility with Pyscript.
        https://hacs-pyscript.readthedocs.io/en/latest/reference.html#task-executor
        """
        if self._pyscript_task_executor is not None:
            return self._pyscript_task_executor(
                super().post_json_response,
                url,
                params=params,
                header_overrides=header_overrides,
                timeout=timeout,
                json=json,
                data=data,
            )

        return super().post_json_response(
            url,
            params=params,
            header_overrides=header_overrides,
            timeout=timeout,
            json=json,
            data=data,
        )

    def _get_records(self, level: int | None = None) -> list[LogRecord]:
        """Get log records from the warehouse.

        Args:
            level (int): the logging level to filter by

        Returns:
            list: a list of log records
        """
        url = f"{self.WAREHOUSE_ENDPOINT}/items?log_host={self.HOST_NAME}"

        if level is not None:
            url += f"&level={level}"

        return [
            LogRecord(
                name=record["logger"],
                level=record["level"],
                pathname=record["file"],
                lineno=record["line"],
                msg=record["message"],
                args=(),
                exc_info=None,  # TODO: add exception info
            )
            for record in cast(WarehouseLogPage, self.get_json_response(url))["items"]
        ]

    @property
    def records(self) -> list[LogRecord]:
        """All records.

        Returns:
            list: a list of all log records
        """
        return self._get_records()

    @property
    def debug_records(self) -> list[LogRecord]:
        """Debug level records.

        Returns:
            list: a list of log records with the level DEBUG
        """
        return self._get_records(DEBUG)

    @property
    def info_records(self) -> list[LogRecord]:
        """Info level records.

        Returns:
            list: a list of log records with the level INFO
        """
        return self._get_records(INFO)

    @property
    def warning_records(self) -> list[LogRecord]:
        """Warning level records.

        Returns:
            list: a list of log records with the level WARNING
        """
        return self._get_records(WARNING)

    @property
    def error_records(self) -> list[LogRecord]:
        """Error level records.

        Returns:
            list: a list of log records with the level ERROR
        """
        return self._get_records(ERROR)

    @property
    def critical_records(self) -> list[LogRecord]:
        """Critical level records.

        Returns:
            list: a list of log records with the level CRITICAL
        """
        return self._get_records(CRITICAL)

    @staticmethod
    def _get_log_hash(record: LogRecord) -> str:
        """Get a hash of the log message.

        Args:
            record (LogRecord): the log record to hash

        Returns:
            str: the hexdigest of the hash
        """
        return md5(record.getMessage().encode()).hexdigest()


def add_warehouse_handler(
    logger: Logger,
    *,
    level: int = DEBUG,
    warehouse_host: str | None = None,
    warehouse_port: int | None = None,
    allow_connection_errors: bool = False,
) -> WarehouseHandler:
    """Add a ListHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        level (int): the logging level to be used for the WarehouseHandler
        warehouse_host (str): the hostname of the Item Warehouse
        warehouse_port (int): the port of the Item Warehouse
        allow_connection_errors (bool): whether to allow connection errors

    Returns:
        WarehouseHandler: the WarehouseHandler that was added to the logger
    """

    wh_handler = WarehouseHandler(
        level=level,
        warehouse_host=warehouse_host,
        warehouse_port=warehouse_port,
        allow_connection_errors=allow_connection_errors,
    )

    logger.addHandler(wh_handler)

    return wh_handler


__all__ = ["WarehouseHandler", "add_warehouse_handler"]
