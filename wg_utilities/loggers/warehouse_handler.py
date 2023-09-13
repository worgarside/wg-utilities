"""Custom handler to allow logging directly into an Item Warehouse."""

from __future__ import annotations

from asyncio import get_running_loop, run
from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime
from hashlib import md5
from http import HTTPStatus
from json import JSONDecodeError, dumps
from logging import DEBUG, WARNING, Formatter, Handler, Logger, LogRecord, getLogger
from os import getenv
from socket import gethostname
from time import gmtime
from traceback import format_exception
from types import TracebackType
from typing import Any, Final, Literal, NotRequired, Protocol, TypeVar, cast

from deepdiff import DeepDiff  # type: ignore[import]
from requests import HTTPError
from requests.exceptions import RequestException
from typing_extensions import TypedDict

from wg_utilities.clients.json_api_client import JsonApiClient, StrBytIntFlt
from wg_utilities.loggers.stream_handler import add_stream_handler

FORMATTER = Formatter(
    fmt="%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)
FORMATTER.converter = gmtime


LOGGER = getLogger(__name__)
LOGGER.setLevel(WARNING)
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


PythonType = int | str | datetime | date | bool | dict | float | None


class FieldDefinition(TypedDict):
    autoincrement: NotRequired[bool | Literal["auto", "ignore_fk"]]
    default: NotRequired[PythonType]
    index: NotRequired[bool | None]
    key: NotRequired[str | None]
    nullable: bool
    primary_key: NotRequired[bool]
    type_kwargs: NotRequired[dict[str, PythonType]]
    type: str
    unique: NotRequired[bool | None]

    display_as: NotRequired[str]


class WarehouseSchema(TypedDict):
    """Type for a Warehouse schema."""

    created_at: NotRequired[str]
    item_name: str
    item_schema: dict[str, FieldDefinition]
    name: str


T = TypeVar("T")


class _PyscriptTaskExecutorProtocol(Protocol[T]):
    async def __call__(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        ...  # pragma: no cover


class HttpErrorHandler:
    def __init__(self, *, allow_connection_errors: bool):
        self._allow_connection_errors = allow_connection_errors

    def __enter__(self) -> HttpErrorHandler:
        return self

    def __exit__(
        self,
        _: type[type] | None,
        exc: Exception | None,
        __: TracebackType | None,
    ) -> bool:
        if isinstance(exc, HTTPError):
            error_detail = exc.response.text
            try:
                if (error_detail := exc.response.json()).get("detail", {}).get(
                    "type"
                ) == "ItemExistsError":
                    return True
            except (AttributeError, LookupError, JSONDecodeError):
                pass

            LOGGER.error(
                "Error posting log to Warehouse: %i %s; %r",
                exc.response.status_code,
                exc.response.reason,
                error_detail,
            )
        elif isinstance(
            exc,
            (ConnectionError | RequestException),
        ):
            LOGGER.error("Error posting log to Warehouse: %r", exc)

            return self._allow_connection_errors
        elif exc is not None:  # pragma: no cover
            raise RuntimeError(f"Unhandled logging exception: {exc!r}") from exc

        return True


http_error_handler = HttpErrorHandler


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

    WAREHOUSE_ENDPOINT: Final = f"/warehouses/{WAREHOUSE_NAME}"

    _WAREHOUSE_SCHEMA: Final[WarehouseSchema] = {
        "name": WAREHOUSE_NAME,
        "item_name": ITEM_NAME,
        "item_schema": {
            "created_at": {
                "nullable": False,
                "type": "double",
            },
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
                "type": "text",
                "type_kwargs": {"length": 16383},
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

        JsonApiClient.__init__(
            self, base_url=self.get_base_url(warehouse_host, warehouse_port)
        )

        self._allow_connection_errors = allow_connection_errors
        self._pyscript_task_executor = pyscript_task_executor

        if self._pyscript_task_executor is not None:
            # Workaround for ensuring the warehouse is still created from Pyscript
            self._post_json_response(
                "/warehouses", json=self._WAREHOUSE_SCHEMA, timeout=5
            )
        else:
            self._initialize_warehouse()

    def _initialize_warehouse(self) -> None:
        schema: WarehouseLog
        try:
            schema = self.get_json_response(  # type: ignore[assignment]
                self.WAREHOUSE_ENDPOINT, timeout=5
            )
        except HTTPError as exc:
            if exc.response.status_code == HTTPStatus.NOT_FOUND:
                schema = self._post_json_response(  # type: ignore[assignment]
                    "/warehouses", json=self._WAREHOUSE_SCHEMA, timeout=5
                )
                LOGGER.info("Created new Warehouse: %r", schema)
        except (
            ConnectionError,
            RequestException,
        ):
            LOGGER.exception("Error creating Warehouse")

            if not self._allow_connection_errors:
                raise
        else:
            LOGGER.info(
                "Warehouse %s already exists - created at %s",
                schema.get("name", None),
                schema.get("created_at", None),
            )

            temp_schema = cast(
                WarehouseSchema,
                {key: value for key, value in schema.items() if key != "created_at"},
            )

            for item_value in temp_schema.get("item_schema", {}).values():
                item_value.pop("display_as", None)

            if diff := DeepDiff(self._WAREHOUSE_SCHEMA, temp_schema):
                raise ValueError(
                    "Warehouse schema does not match expected schema: "
                    + dumps(diff, default=repr)
                )

    def emit(self, record: LogRecord) -> None:
        """Add log record to the internal record store.

        Args:
            record (LogRecord): the new log record being "emitted"
        """

        log_payload = {
            "created_at": record.created,
            "exception_message": None,
            "exception_type": None,
            "exception_traceback": None,
            "file": record.pathname,
            "level": record.levelno,
            "line": record.lineno,
            "log_hash": self.get_log_hash(record),
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

        self._post_json_response(
            f"{self.WAREHOUSE_ENDPOINT}/items", json=log_payload, timeout=5
        )

    def _post_json_response(
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
    ) -> WarehouseLog | WarehouseLogPage | None:
        """Post a JSON response to the warehouse.

        This is overridden to allow compatibility with Pyscript.
        https://hacs-pyscript.readthedocs.io/en/latest/reference.html#task-executor
        """
        if self._pyscript_task_executor is not None:
            self._run_pyscript_task_executor(
                self.post_json_response,
                url,
                params=params,
                header_overrides=header_overrides,
                timeout=timeout,
                json=json,
                data=data,
            )
            return None

        with http_error_handler(allow_connection_errors=self._allow_connection_errors):
            return self.post_json_response(
                url,
                params=params,
                header_overrides=header_overrides,
                timeout=timeout,
                json=json,
                data=data,
            )

        return None

    async def _async_task_executor(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None:
        if (
            not hasattr(self, "_pyscript_task_executor")
            or not self._pyscript_task_executor
        ):
            raise NotImplementedError("Pyscript task executor is not defined")

        with http_error_handler(allow_connection_errors=self._allow_connection_errors):
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
            return

        run(self._async_task_executor(func, *args, **kwargs))

    @staticmethod
    def get_base_url(host: str | None, port: int | None) -> str:
        """Get the base URL for the Item Warehouse.

        Args:
            host (str): the hostname of the Item Warehouse
            port (int): the port of the Item Warehouse

        Returns:
            str: the base URL for the Item Warehouse
        """

        host = host or str(getenv("ITEM_WAREHOUSE_HOST", "http://homeassistant.local"))
        port = port or int(getenv("ITEM_WAREHOUSE_PORT", "0"))

        if port:
            host += f":{port}"

        host += "/v1"

        return host

    @staticmethod
    def get_log_hash(record: LogRecord) -> str:
        """Get a hash of the log message.

        Args:
            record (LogRecord): the log record to hash

        Returns:
            str: the hexdigest of the hash
        """
        return md5(record.getMessage().encode(), usedforsecurity=False).hexdigest()


def add_warehouse_handler(
    logger: Logger,
    *,
    level: int = DEBUG,
    warehouse_host: str | None = None,
    warehouse_port: int | None = None,
    allow_connection_errors: bool = False,
    pyscript_task_executor: _PyscriptTaskExecutorProtocol[
        WarehouseLog | WarehouseLogPage
    ]
    | None = None,
) -> WarehouseHandler:
    """Add a ListHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        level (int): the logging level to be used for the WarehouseHandler
        warehouse_host (str): the hostname of the Item Warehouse
        warehouse_port (int): the port of the Item Warehouse
        allow_connection_errors (bool): whether to allow connection errors
        pyscript_task_executor (Callable): the Pyscript task executor (if applicable)

    Returns:
        WarehouseHandler: the WarehouseHandler that was added to the logger
    """

    for handler in logger.handlers:
        if isinstance(
            handler, WarehouseHandler
        ) and handler.base_url == WarehouseHandler.get_base_url(
            warehouse_host, warehouse_port
        ):
            LOGGER.warning("WarehouseHandler already exists for %s", handler.base_url)
            return handler

    wh_handler = WarehouseHandler(
        level=level,
        warehouse_host=warehouse_host,
        warehouse_port=warehouse_port,
        allow_connection_errors=allow_connection_errors,
        pyscript_task_executor=pyscript_task_executor,
    )

    logger.addHandler(wh_handler)

    return wh_handler


__all__ = ["WarehouseHandler", "add_warehouse_handler"]
