"""Unit test fixtures for the loggers module."""
from __future__ import annotations

from http import HTTPStatus
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Logger,
    LogRecord,
    getLevelName,
    getLogger,
)

from pytest import FixtureRequest, fixture
from requests_mock import Mocker

from tests.conftest import YieldFixture
from wg_utilities.loggers import ListHandler
from wg_utilities.loggers.warehouse_handler import WarehouseHandler


@fixture(scope="function", name="list_handler")
def _list_handler() -> ListHandler:
    """Fixture for creating a ListHandler instance."""
    l_handler = ListHandler(log_ttl=None)
    l_handler.setLevel(DEBUG)
    return l_handler


@fixture(scope="function", name="list_handler_prepopulated")
def _list_handler_prepopulated(
    logger: Logger,
    list_handler: ListHandler,
    sample_log_record_messages_with_level: list[tuple[int, str]],
) -> ListHandler:
    """Fixture for creating a ListHandler instance with a pre-populated list."""
    logger.handlers.clear()
    logger.addHandler(list_handler)

    for level, message in sample_log_record_messages_with_level:
        logger.log(level, message)

    return list_handler


@fixture(scope="function", name="logger")
def _logger(
    request: FixtureRequest,
    warehouse_handler: WarehouseHandler,
    list_handler: ListHandler,
) -> YieldFixture[Logger]:
    """Fixture for creating a logger."""

    _logger = getLogger(request.node.name)
    _logger.setLevel(DEBUG)
    _logger.handlers.clear()

    if handler_marker := request.node.get_closest_marker("add_handler"):
        handlers = {
            "list_handler": list_handler,
            "warehouse_handler": warehouse_handler,
        }

        for handler_name in handler_marker.args:
            _logger.addHandler(handlers[handler_name])

    yield _logger

    _logger.handlers.clear()


@fixture(scope="function", name="sample_log_record")
def _sample_log_record() -> LogRecord:
    """Fixture for creating a sample log record."""
    return LogRecord(
        name="test_logger",
        level=10,
        pathname=__file__,
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
        func=None,
    )


LOG_LEVELS = [DEBUG, INFO, WARNING, ERROR, CRITICAL]

SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL = [
    (level, f"Test log message #{i} at level {getLevelName(level)}")
    for i, level in enumerate(LOG_LEVELS * 5)
]

SAMPLE_LOG_RECORDS = [
    LogRecord(
        name="test",
        level=record[0],
        pathname="test",
        lineno=1,
        msg=record[1],
        args=(),
        exc_info=None,
    )
    for record in SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL
]


@fixture(scope="function", name="sample_log_record_messages_with_level")
def _sample_log_record_messages_with_level() -> list[tuple[int, str]]:
    """Fixture for creating a list of sample log records."""
    return SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL


WAREHOUSE_SCHEMA = {
    "name": "lumberyard",
    "created_at": "2023-07-26T17:56:26.951515",
    "item_name": "log",
    "item_schema": {
        "created_at": {"nullable": False, "type": "float"},
        "exception_message": {
            "nullable": True,
            "type_kwargs": {"length": 2048},
            "type": "string",
        },
        "exception_type": {
            "nullable": True,
            "type_kwargs": {"length": 64},
            "type": "string",
        },
        "exception_traceback": {
            "nullable": True,
            "type_kwargs": {"length": 2048},
            "type": "string",
        },
        "file": {
            "nullable": False,
            "type_kwargs": {"length": 255},
            "type": "string",
        },
        "level": {"nullable": False, "type": "integer"},
        "line": {"nullable": False, "type": "integer"},
        "log_hash": {
            "nullable": False,
            "primary_key": True,
            "type_kwargs": {"length": 32},
            "type": "string",
        },
        "log_host": {
            "default": "func:client_ip",
            "nullable": False,
            "primary_key": True,
            "type_kwargs": {"length": 45},
            "type": "string",
        },
        "logger": {
            "nullable": False,
            "primary_key": True,
            "type_kwargs": {"length": 255},
            "type": "string",
        },
        "message": {
            "nullable": False,
            "type_kwargs": {"length": 2048},
            "type": "string",
        },
        "module": {
            "nullable": False,
            "type_kwargs": {"length": 255},
            "type": "string",
        },
        "process": {
            "nullable": False,
            "type_kwargs": {"length": 255},
            "type": "string",
        },
        "thread": {
            "nullable": False,
            "type_kwargs": {"length": 255},
            "type": "string",
        },
    },
}


@fixture(scope="function", name="warehouse_handler")
def _warehouse_handler(
    mock_requests: Mocker,  # pylint: disable=unused-argument
) -> YieldFixture[WarehouseHandler]:
    """Fixture for creating a WarehouseHandler instance."""

    lumberyard_base_url = "https://item-warehouse.com"

    lumberyard_url = "/".join(
        [
            lumberyard_base_url,
            "v1",
            "warehouses",
            "lumberyard",
        ]
    )

    mock_requests.get(
        lumberyard_url,
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=WAREHOUSE_SCHEMA,
    )

    for level in LOG_LEVELS:
        mock_requests.get(
            f"{lumberyard_url}/items?level={level}",
            status_code=HTTPStatus.OK,
            reason=HTTPStatus.OK.phrase,
            json={
                "items": [
                    {
                        "created_at": "2023-07-26T17:56:26.951515",
                        "file": __file__,
                        "level": level,
                        "line": 0,
                        "log_hash": "d41d8cd98f00b204e9800998ecf8427e",
                        "log_host": "testhost",
                        "logger": "test_logger",
                        "message": f"test message @ level {level}",
                        "module": "test_loggers",
                        "process": "MainProcess",
                        "thread": "MainThread",
                    }
                ]
            },
        )

    _warehouse_handler = WarehouseHandler(
        level="DEBUG", warehouse_host=lumberyard_base_url, warehouse_port=None
    )

    yield _warehouse_handler

    _warehouse_handler.close()


@fixture(scope="function", name="mock_requests", autouse=True)
def _mock_requests(
    mock_requests_root: Mocker,
) -> YieldFixture[Mocker]:
    """Fixture for mocking sync HTTP requests."""

    yield mock_requests_root
