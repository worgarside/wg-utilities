"""Custom handler to allow logging directly into an Item Warehouse."""

from __future__ import annotations

import atexit
from http import HTTPStatus
from json import dumps
from logging import DEBUG, Logger, LogRecord, getLogger
from logging.handlers import QueueHandler
from multiprocessing import Queue
from os import getenv
from typing import Literal

from requests import HTTPError, post
from requests.exceptions import RequestException

from wg_utilities.functions.decorators import backoff
from wg_utilities.loggers.item_warehouse.flushable_queue_listener import (
    FlushableQueueListener,
)

from .base_handler import BaseWarehouseHandler, LogPayload, WarehouseSchema

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)

BACKOFF_MAX_TRIES = int(getenv("WAREHOUSE_HANDLER_BACKOFF_MAX_TRIES", "0"))
BACKOFF_TIMEOUT = int(getenv("WAREHOUSE_HANDLER_BACKOFF_TIMEOUT", "0"))

LOG_QUEUE: Queue[LogRecord | None] = Queue()


class WarehouseHandler(BaseWarehouseHandler):
    """Custom handler to allow logging directly into an Item Warehouse.

    https://github.com/worgarside/addon-item-warehouse-api
    https://github.com/worgarside/addon-item-warehouse-website

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
        initialize_warehouse: bool = False,
    ) -> None:
        """Initialize the handler and Log Warehouse."""

        super().__init__(
            level=level,
            warehouse_host=warehouse_host,
            warehouse_port=warehouse_port,
        )

        if initialize_warehouse:
            self.initialize_warehouse()

    def emit(self, record: LogRecord) -> None:
        """Add log record to the internal record store.

        Args:
            record (LogRecord): the new log record being "emitted"
        """

        log_payload = self.get_log_payload(record)

        self.post_with_backoff(log_payload)

    def initialize_warehouse(self) -> None:
        """Create a new warehouse or validate an existing one."""
        try:
            schema: WarehouseSchema = self.get_json_response(  # type: ignore[assignment]
                self.WAREHOUSE_ENDPOINT,
                timeout=5,
            )
        except HTTPError as exc:
            if (
                exc.response is not None
                and exc.response.status_code == HTTPStatus.NOT_FOUND
            ):
                schema = self.post_json_response(  # type: ignore[assignment]
                    "/warehouses",
                    json=self._WAREHOUSE_SCHEMA,
                    timeout=5,
                )
                LOGGER.info("Created new Warehouse: %r", schema)
        except Exception:
            LOGGER.exception("Error creating Warehouse")
        else:
            LOGGER.info(
                "Warehouse %s already exists - created at %s",
                schema.get("name", None),
                schema.get("created_at", None),
            )

            schema_types = {
                k: v["type"] for k, v in schema.get("item_schema", {}).items()
            }

            if schema_types != self._WAREHOUSE_TYPES:
                raise ValueError(
                    "Warehouse types do not match expected types: "
                    + dumps(
                        {
                            k: {"expected": v, "actual": schema_types.get(k)}
                            for k, v in self._WAREHOUSE_TYPES.items()
                            if v != schema_types.get(k)
                        },
                        default=str,
                    ),
                )

    @backoff(
        RequestException,
        logger=LOGGER,
        max_tries=BACKOFF_MAX_TRIES,
        timeout=BACKOFF_TIMEOUT,
    )
    def post_with_backoff(self, log_payload: LogPayload, /) -> None:
        """Post a JSON response to the warehouse, with backoff applied."""

        res = post(
            f"{self.base_url}{self.ITEM_ENDPOINT}",
            timeout=60,
            json=log_payload,
        )

        if res.status_code == HTTPStatus.CONFLICT:
            return

        if (
            str(res.status_code).startswith("4")
            and res.status_code != HTTPStatus.TOO_MANY_REQUESTS
        ):
            LOGGER.error(
                "Permanent error posting log to warehouse (%s %s): %s",
                res.status_code,
                res.reason,
                res.text,
            )
            return

        res.raise_for_status()


class _QueueHandler(QueueHandler):
    """QueueHandler subclass to allow comparison of WarehouseHandlers."""

    def __init__(
        self,
        queue: Queue[LogRecord | None],
        warehouse_handler: WarehouseHandler,
    ) -> None:
        super().__init__(queue)

        self.warehouse_handler = warehouse_handler


def add_warehouse_handler(
    logger: Logger,
    *,
    level: int = DEBUG,
    warehouse_host: str | None = None,
    warehouse_port: int | None = None,
    initialize_warehouse: bool = False,
    disable_queue: bool = False,
) -> WarehouseHandler:
    """Add a WarehouseHandler to an existing logger.

    Args:
        logger (Logger): the logger to add a file handler to
        level (int): the logging level to be used for the WarehouseHandler
        warehouse_host (str): the hostname of the Item Warehouse
        warehouse_port (int): the port of the Item Warehouse
        initialize_warehouse (bool): whether to initialize the Warehouse
        disable_queue (bool): whether to disable the queue for the WarehouseHandler

    Returns:
        WarehouseHandler: the WarehouseHandler that was added to the logger
    """

    wh_handler = WarehouseHandler(
        level=level,
        warehouse_host=warehouse_host,
        warehouse_port=warehouse_port,
        initialize_warehouse=initialize_warehouse,
    )

    if disable_queue:
        for handler in logger.handlers:
            if isinstance(
                handler,
                WarehouseHandler,
            ) and handler.base_url == WarehouseHandler.get_base_url(
                warehouse_host,
                warehouse_port,
            ):
                LOGGER.warning("WarehouseHandler already exists for %s", handler.base_url)
                return handler

        logger.addHandler(wh_handler)
        return wh_handler

    for handler in logger.handlers:
        if isinstance(handler, _QueueHandler) and handler.warehouse_handler == wh_handler:
            LOGGER.warning(
                "WarehouseHandler already exists for %s",
                handler.warehouse_handler.base_url,
            )
            return handler.warehouse_handler

    listener = FlushableQueueListener(LOG_QUEUE, wh_handler)
    listener.start()

    q_handler = _QueueHandler(LOG_QUEUE, wh_handler)
    q_handler.setLevel(level)

    logger.addHandler(q_handler)

    # Ensure the queue worker is stopped when the program exits
    atexit.register(LOGGER.info, "Stopped WarehouseHandler")
    atexit.register(listener.flush_and_stop)
    atexit.register(LOG_QUEUE.put, None)  # Processed in reverse order

    return wh_handler


__all__ = ["WarehouseHandler", "add_warehouse_handler"]
