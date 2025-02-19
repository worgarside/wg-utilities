"""Unit tests for the WarehouseHandler class."""

from __future__ import annotations

from hashlib import md5
from http import HTTPStatus
from json import dumps
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Handler, Logger, LogRecord
from socket import gethostname
from typing import TYPE_CHECKING
from unittest.mock import ANY, patch

import pytest

from tests.conftest import TestError, assert_mock_requests_request_history
from tests.unit.loggers.conftest import (
    IWH_DOT_COM,
    SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL,
    SAMPLE_LOG_RECORDS,
    WAREHOUSE_SCHEMA,
)
from wg_utilities.clients.json_api_client import JsonApiClient
from wg_utilities.loggers import WarehouseHandler

if TYPE_CHECKING:
    from requests_mock import Mocker


def test_instantiation() -> None:
    """Test that the WarehouseHandler class can be instantiated."""
    wh_handler = WarehouseHandler()

    assert isinstance(wh_handler, WarehouseHandler)
    assert isinstance(wh_handler, Handler)
    assert isinstance(wh_handler, JsonApiClient)


def test_initialize_warehouse_new_warehouse(mock_requests: Mocker) -> None:
    """Test that the _initialize_warehouse method works correctly."""
    mock_requests.get(
        f"{IWH_DOT_COM}/v1/warehouses/lumberyard",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with patch.object(
        WarehouseHandler,
        "post_json_response",
        return_value=WAREHOUSE_SCHEMA,
    ) as mock_post_json_response:
        _ = WarehouseHandler(
            warehouse_host=IWH_DOT_COM,
            warehouse_port=0,
            initialize_warehouse=True,
        )

    mock_post_json_response.assert_called_once_with(
        "/warehouses",
        timeout=5,
        json=WarehouseHandler._WAREHOUSE_SCHEMA,
    )


DEFAULT_ITEM_URL = "http://homeassistant.local:8002/v1/warehouses/lumberyard"


def test_initialize_warehouse_already_exists(
    caplog: pytest.LogCaptureFixture,
    mock_requests: Mocker,
) -> None:
    """Test that the _initialize_warehouse method works correctly."""
    from wg_utilities.loggers.item_warehouse.warehouse_handler import LOGGER

    LOGGER.setLevel(INFO)
    caplog.set_level(INFO)

    mock_requests.get(
        # Default URL
        DEFAULT_ITEM_URL,
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=WAREHOUSE_SCHEMA,
    )

    _ = WarehouseHandler(initialize_warehouse=True)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": DEFAULT_ITEM_URL,
                "method": "GET",
                "headers": {},
            },
        ],
    )

    assert (
        caplog.records[0].message
        == "Warehouse lumberyard already exists - created at 2023-07-26T17:56:26.951515"
    )


def test_initialize_warehouse_already_exists_but_wrong_schema(
    mock_requests: Mocker,
) -> None:
    """Test that the _initialize_warehouse method works correctly."""
    mock_requests.get(
        # Default URL
        DEFAULT_ITEM_URL,
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"invalid": "schema"},
    )

    with pytest.raises(ValueError) as exc_info:
        _ = WarehouseHandler(initialize_warehouse=True)

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": DEFAULT_ITEM_URL,
                "method": "GET",
                "headers": {},
            },
        ],
    )

    mismatches = {
        "created_at": {"expected": "double", "actual": None},
        "exception_message": {"expected": "string", "actual": None},
        "exception_type": {"expected": "string", "actual": None},
        "exception_traceback": {"expected": "text", "actual": None},
        "file": {"expected": "string", "actual": None},
        "level": {"expected": "integer", "actual": None},
        "line": {"expected": "integer", "actual": None},
        "log_hash": {"expected": "string", "actual": None},
        "log_host": {"expected": "string", "actual": None},
        "logger": {"expected": "string", "actual": None},
        "message": {"expected": "string", "actual": None},
        "module": {"expected": "string", "actual": None},
        "process": {"expected": "string", "actual": None},
        "thread": {"expected": "string", "actual": None},
    }

    assert (
        str(exc_info.value)
        == f"Warehouse types do not match expected types: {dumps(mismatches)}"
    )


def test_initialize_warehouse_exception(
    mock_requests: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the _initialize_warehouse method works correctly."""
    mock_requests.get(
        # Default URL
        DEFAULT_ITEM_URL,
        exc=TestError("Test exception"),
    )

    _ = WarehouseHandler(initialize_warehouse=True)

    assert caplog.records[-1].message == "Error creating Warehouse"
    assert caplog.records[-1].exc_info[0] == TestError  # type: ignore[index]
    assert caplog.records[-1].exc_info[1].args == ("Test exception",)  # type: ignore[index,union-attr]
    assert caplog.records[-1].levelno == ERROR


@pytest.mark.add_handler("warehouse_handler")
@pytest.mark.parametrize(
    ("level", "message", "record"),
    [
        (level, message, record)
        for ((level, message), record) in zip(
            SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL,
            SAMPLE_LOG_RECORDS,
            strict=False,
        )
    ],
)
def test_emit(level: int, message: str, logger: Logger, record: LogRecord) -> None:
    """Test that the emit method sends the correct payload to the warehouse."""
    log_payload = {
        "created_at": ANY,
        "exception_message": None,
        "exception_type": None,
        "exception_traceback": None,
        "file": __file__,
        "level": level,
        "line": ANY,
        "log_hash": md5(message.encode(), usedforsecurity=False).hexdigest(),
        "log_host": gethostname(),
        "logger": logger.name,
        "message": message,
        "module": "test__warehouse_handler",
        "process": "MainProcess",
        "thread": "MainThread",
    }

    with (
        patch.object(
            WarehouseHandler,
            "get_log_payload",
            return_value=log_payload,
        ) as mock_get_log_payload,
        patch.object(
            WarehouseHandler,
            "post_with_backoff",
        ) as mock_post_with_backoff,
    ):
        logger.log(level, message)

    mock_get_log_payload.assert_called_once()

    emitted_record = mock_get_log_payload.call_args[0][0]

    assert emitted_record.levelno == record.levelno
    assert emitted_record.levelname == record.levelname
    assert emitted_record.msg == record.msg
    assert emitted_record.args == record.args
    assert emitted_record.exc_info == record.exc_info
    assert emitted_record.exc_text == record.exc_text
    assert emitted_record.stack_info == record.stack_info

    mock_post_with_backoff.assert_called_once_with(log_payload)


@pytest.mark.add_handler("warehouse_handler")
def test_post_with_backoff_duplicate_record(logger: Logger) -> None:
    """Test that the post_with_backoff method doesn't throw an error for duplicate records."""
    with patch("wg_utilities.loggers.item_warehouse.warehouse_handler.post") as mock_post:
        mock_post.return_value.status_code = HTTPStatus.CONFLICT

        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")

    assert mock_post.call_count == 6

    mock_post.return_value.raise_for_status.assert_not_called()


@pytest.mark.parametrize(
    "response_status",
    [
        HTTPStatus.OK,
        HTTPStatus.TOO_MANY_REQUESTS,
    ],
)
@pytest.mark.add_handler("warehouse_handler")
def test_post_with_backoff(logger: Logger, response_status: HTTPStatus) -> None:
    """Test that the post_with_backoff works (ignoring actual backoff functionality)."""
    with patch("wg_utilities.loggers.item_warehouse.warehouse_handler.post") as mock_post:
        mock_post.return_value.status_code = response_status

        logger.debug("Debug log")
        logger.info("Info log")
        logger.warning("Warning log")
        logger.error("Error log")
        logger.critical("Critical log")
        logger.exception(TestError("Exception log"))

    assert mock_post.call_count == 6

    assert all(
        mock_post.call_args_list[i][1]["json"]["level"] == level
        for i, level in enumerate([DEBUG, INFO, WARNING, ERROR, CRITICAL, ERROR])
    )

    assert mock_post.return_value.raise_for_status.call_count == 6


@pytest.mark.parametrize(
    "response_status",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.METHOD_NOT_ALLOWED,
        HTTPStatus.NOT_ACCEPTABLE,
        HTTPStatus.PROXY_AUTHENTICATION_REQUIRED,
        HTTPStatus.REQUEST_TIMEOUT,
        HTTPStatus.GONE,
        HTTPStatus.LENGTH_REQUIRED,
        HTTPStatus.PRECONDITION_FAILED,
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        HTTPStatus.REQUEST_URI_TOO_LONG,
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE,
        HTTPStatus.EXPECTATION_FAILED,
        HTTPStatus.MISDIRECTED_REQUEST,
        HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
    ],
)
@pytest.mark.add_handler("warehouse_handler")
def test_post_with_backoff_permanent_failure(
    logger: Logger,
    caplog: pytest.LogCaptureFixture,
    response_status: HTTPStatus,
) -> None:
    """Test that 4XX status codes aren't backed off."""
    with (
        patch(
            "wg_utilities.loggers.item_warehouse.warehouse_handler.post",
        ) as mock_post,
        caplog.at_level("ERROR"),
    ):
        mock_post.return_value.status_code = response_status
        mock_post.return_value.reason = response_status.phrase
        mock_post.return_value.text = "!!!"

        logger.info("Info log")

    assert mock_post.call_count == 1

    mock_post.return_value.raise_for_status.assert_not_called()

    assert (
        f"Permanent error posting log to warehouse ({response_status} {response_status.phrase}): !!!"
        == caplog.records[-1].message
    )
