"""Custom handler to allow logging directly into an Item Warehouse."""

from __future__ import annotations

from datetime import date, datetime
from hashlib import md5
from logging import DEBUG, Handler, LogRecord, getLogger
from os import getenv
from socket import gethostname
from traceback import format_exception
from typing import Any, Final, Literal, NotRequired, TypedDict

from wg_utilities.clients import JsonApiClient

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

ITEM_EXISTS_ERROR: Final = "ItemExistsError"


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


PythonType = int | str | datetime | date | bool | dict[str, Any] | float | None


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


class LogPayload(TypedDict):
    """Type for a log payload."""

    created_at: float
    exception_message: str | None
    exception_type: str | None
    exception_traceback: str | None
    file: str
    level: int
    line: int
    log_hash: str
    log_host: str
    logger: str
    message: str
    module: str
    process: str | None
    thread: str | None


class BaseWarehouseHandler(Handler, JsonApiClient[WarehouseLog | WarehouseLogPage]):
    """Custom handler to allow logging directly into an Item Warehouse.

    https://github.com/worgarside/addon-item-warehouse-api
    https://github.com/worgarside/addon-item-warehouse-website

    The primary key of the log warehouse is a combination of:
        - log_hash (message content)
        - logger (name of the logger)
        - log_host (hostname of the machine the log was generated on)

    This means that the same log message from the same host will only be stored once.
    """

    HOST_NAME: Final = gethostname()

    ITEM_NAME: Final = "log"
    WAREHOUSE_NAME: Final = "lumberyard"

    WAREHOUSE_ENDPOINT: Final = f"/warehouses/{WAREHOUSE_NAME}"
    ITEM_ENDPOINT: Final = f"{WAREHOUSE_ENDPOINT}/items"

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

    _WAREHOUSE_TYPES: Final[dict[str, str]] = {
        k: v["type"] for k, v in _WAREHOUSE_SCHEMA["item_schema"].items()
    }

    def __init__(
        self,
        *,
        level: int | Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        warehouse_host: str | None = None,
        warehouse_port: int | None = None,
    ) -> None:
        """Initialize the handler."""

        Handler.__init__(self, level=level)

        JsonApiClient.__init__(
            self,
            base_url=self.get_base_url(warehouse_host, warehouse_port),
        )

    def emit(self, _: LogRecord) -> None:  # noqa: D102
        raise NotImplementedError("Don't use the base handler directly.")

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
        port = port if port is not None else int(getenv("ITEM_WAREHOUSE_PORT", "8002"))

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

    @staticmethod
    def get_log_payload(record: LogRecord) -> LogPayload:
        """Get a log payload from a log record.

        Args:
            record (LogRecord): the log record to convert

        Returns:
            LogPayload: the converted log payload
        """

        log_payload: LogPayload = {
            "created_at": record.created,
            "exception_message": None,
            "exception_type": None,
            "exception_traceback": None,
            "file": record.pathname,
            "level": record.levelno,
            "line": record.lineno,
            "log_hash": BaseWarehouseHandler.get_log_hash(record),
            "log_host": BaseWarehouseHandler.HOST_NAME,
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
                format_exception(record.exc_info[1]),
            )

        return log_payload

    def __eq__(self, other: object) -> bool:
        """Compare two WarehouseHandlers for equality."""

        if not isinstance(other, BaseWarehouseHandler):  # pragma: no cover
            return NotImplemented

        return self.base_url == other.base_url and self.level == other.level

    def __hash__(self) -> int:  # noqa: D105
        return super().__hash__()

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"<{self.__class__.__name__}(base_url={self.base_url}, level={self.level})>"
        )


__all__ = ["BaseWarehouseHandler"]
