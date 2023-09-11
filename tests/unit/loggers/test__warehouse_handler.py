# pylint: disable=protected-access
"""Unit tests for the WarehouseHandler class."""


from __future__ import annotations

from asyncio import iscoroutine
from collections.abc import Callable
from hashlib import md5
from http import HTTPStatus
from json import dumps
from logging import ERROR, INFO, Handler, Logger, LogRecord
from socket import gethostname
from traceback import format_exc
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import pytest
from freezegun import freeze_time
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException
from requests_mock import ANY as REQUESTS_MOCK_ANY
from requests_mock import Mocker

from tests.conftest import TestError, assert_mock_requests_request_history
from tests.unit.loggers.conftest import (
    SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL,
    SAMPLE_LOG_RECORDS,
    WAREHOUSE_SCHEMA,
)
from wg_utilities.clients.json_api_client import JsonApiClient
from wg_utilities.loggers.warehouse_handler import WarehouseHandler


def test_instantiation() -> None:
    """Test that the WarehouseHandler class can be instantiated."""

    with patch.object(
        WarehouseHandler, "_initialize_warehouse"
    ) as mock_initialize_warehouse:
        wh_handler = WarehouseHandler()

    mock_initialize_warehouse.assert_called_once()

    assert isinstance(wh_handler, WarehouseHandler)
    assert isinstance(wh_handler, Handler)
    assert isinstance(wh_handler, JsonApiClient)


def test_initialize_warehouse_new_warehouse(mock_requests: Mocker) -> None:
    """Test that the _initialize_warehouse method works correctly."""

    mock_requests.get(
        "https://item-warehouse.com/v1/warehouses/lumberyard",
        status_code=HTTPStatus.NOT_FOUND,
        reason=HTTPStatus.NOT_FOUND.phrase,
    )

    with patch.object(
        WarehouseHandler, "post_json_response", return_value=WAREHOUSE_SCHEMA
    ) as mock_post_json_response:
        _ = WarehouseHandler(warehouse_host="https://item-warehouse.com")

    mock_post_json_response.assert_called_once_with(
        "/warehouses",
        params=None,
        header_overrides=None,
        timeout=5,
        json=WarehouseHandler._WAREHOUSE_SCHEMA,
        data=None,
    )


def test_initialize_warehouse_already_exists(
    caplog: pytest.LogCaptureFixture, mock_requests: Mocker
) -> None:
    # pylint: disable=import-outside-toplevel
    """Test that the _initialize_warehouse method works correctly."""
    from wg_utilities.loggers.warehouse_handler import LOGGER

    LOGGER.setLevel(INFO)
    caplog.set_level(INFO)

    mock_requests.get(
        # Default URL
        "http://homeassistant.local/v1/warehouses/lumberyard",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=WAREHOUSE_SCHEMA,
    )

    _ = WarehouseHandler()

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "http://homeassistant.local/v1/warehouses/lumberyard",
                "method": "GET",
                "headers": {},
            }
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
        "http://homeassistant.local/v1/warehouses/lumberyard",
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json={"invalid": "schema"},
    )

    with pytest.raises(ValueError) as exc_info:
        _ = WarehouseHandler()

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "http://homeassistant.local/v1/warehouses/lumberyard",
                "method": "GET",
                "headers": {},
            }
        ],
    )

    expected_diff = {
        "dictionary_item_added": "[root['invalid']]",
        "dictionary_item_removed": "[root['name'], root['item_name'], root['item_schema']]",
    }

    assert (
        str(exc_info.value)
        == f"Warehouse schema does not match expected schema: {dumps(expected_diff)}"
    )


@pytest.mark.parametrize(
    ("log_record", "expected_hash"),
    tuple(
        zip(
            SAMPLE_LOG_RECORDS,
            (
                "1e05cd0ed066d50b1a0802789fadee56",
                "86c198e652158bd68f41d82975800377",
                "70e883e4c5ce4a578d29234911966b42",
                "a7a101ea5bf832a39490df7a3f139c86",
                "045d016612faee5da40656706f6145fb",
                "1fe2cbaaabdf9245d87a78bc7c0fe3bf",
                "a65a1ab074fc98617c7738e5dd651ad4",
                "a2f9bddc9196b43f414b191294103300",
                "ec83769b693de73001cfd7151dc05d00",
                "e7952fd7d16df1e52eafbc1614136234",
                "d9de655c92a41e55550eccc098400e23",
                "8d5e977944ee6c814ed959b898a3e7d6",
                "8e248ec9bba275d283bec6b46ff837b6",
                "1afd92270041f67a6ba3bb7660a5c8f8",
                "babbcfc4e59dffdeb903b188f0549d72",
                "a9643698bd19c7ddd4d040702e30ac92",
                "1ad218249f2e2a115aebfd0aa17867f9",
                "5b336519ff0f081025e7db88ff82cd70",
                "c213821a31d071ba4b73f7c91cb39cd8",
                "14964924a99d81b87f37b41d1a286618",
                "81034992bac8ad040352253a9df6163e",
                "cb2761c9be3acd1fae0816bcf97c0bd6",
                "50f3edd190b2d395d68c9606383d954d",
                "3d309702a096c3fa6620cb001ec90e05",
                "9e821dc5cb3cc36a2c5c91ec9b18a3bd",
            ),
            strict=False,
        )
    ),
)
def test_get_log_hash(log_record: LogRecord, expected_hash: str) -> None:
    """Test that the get_log_hash method returns consistent results."""

    assert WarehouseHandler.get_log_hash(log_record) == expected_hash


@pytest.mark.add_handler("warehouse_handler")
@pytest.mark.parametrize(("level", "message"), SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL)
def test_emit(level: int, message: str, logger: Logger) -> None:
    """Test that the emit method sends the correct payload to the warehouse."""

    with patch.object(
        WarehouseHandler, "post_json_response"
    ) as mock_post_json_response:
        logger.log(level, message)

    expected_log_payload = {
        "created_at": ANY,
        "file": __file__,
        "level": level,
        "line": ANY,
        "log_hash": md5(
            message.encode(),
        ).hexdigest(),
        "log_host": gethostname(),
        "logger": logger.name,
        "message": message,
        "module": "test__warehouse_handler",
        "process": "MainProcess",
        "thread": "MainThread",
    }

    mock_post_json_response.assert_called_once_with(
        "/warehouses/lumberyard/items",
        params=None,
        header_overrides=None,
        timeout=5,
        json=expected_log_payload,
        data=None,
    )


@pytest.mark.add_handler("warehouse_handler")
def test_emit_exception(logger: Logger) -> None:
    """Test exception info is included for exceptions."""

    tb = None
    with patch.object(
        WarehouseHandler, "post_json_response"
    ) as mock_post_json_response:
        try:
            raise TestError("Test Error")  # noqa: TRY301
        except TestError:
            logger.exception(":(")
            tb = format_exc()

    mock_post_json_response.assert_called_once_with(
        "/warehouses/lumberyard/items",
        params=None,
        header_overrides=None,
        timeout=5,
        json={
            "created_at": ANY,
            "file": __file__,
            "level": ERROR,
            "line": ANY,
            "log_hash": md5(
                b":(",
            ).hexdigest(),
            "log_host": gethostname(),
            "logger": logger.name,
            "message": ":(",
            "module": "test__warehouse_handler",
            "process": "MainProcess",
            "thread": "MainThread",
            "exception_type": "TestError",
            "exception_message": "Test Error",
            "exception_traceback": tb,
        },
        data=None,
    )


@pytest.mark.add_handler("warehouse_handler")
def test_emit_duplicate_record(
    caplog: pytest.LogCaptureFixture, logger: Logger, mock_requests: Mocker
) -> None:
    """Test that the emit method doesn't throw an error for duplicate records."""

    caplog.set_level(ERROR)

    mock_requests.post(
        "https://item-warehouse.com/v1/warehouses/lumberyard/items",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        json={"detail": {"type": "ItemExistsError"}},
    )

    logger.info("Info log")
    logger.info("Info log")
    logger.info("Info log")
    logger.info("Info log")
    logger.info("Info log")

    assert not caplog.records


@pytest.mark.add_handler("warehouse_handler")
def test_emit_http_error(
    caplog: pytest.LogCaptureFixture, logger: Logger, mock_requests: Mocker
) -> None:
    """Test that the emit method logs other HTTP errors."""

    caplog.set_level(ERROR)

    mock_requests.post(
        "https://item-warehouse.com/v1/warehouses/lumberyard/items",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        json={"detail": {"type": "OtherError"}},
    )

    logger.info("Info log")

    assert caplog.records[
        0
    ].message == "Error posting log to Warehouse: 500 Internal Server Error; " + str(
        {"detail": {"type": "OtherError"}}
    )


@pytest.mark.add_handler("warehouse_handler")
def test_emit_bad_response_schema(
    caplog: pytest.LogCaptureFixture, logger: Logger, mock_requests: Mocker
) -> None:
    """Test that the emit method logs other HTTP errors, even with an unknown schema."""

    caplog.set_level(ERROR)

    mock_requests.post(
        "https://item-warehouse.com/v1/warehouses/lumberyard/items",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        json={"detail": ["not", "a", "dict"]},
    )

    logger.info("Info log")

    assert caplog.records[
        0
    ].message == "Error posting log to Warehouse: 500 Internal Server Error; " + str(
        {"detail": ["not", "a", "dict"]}
    )


@pytest.mark.add_handler("warehouse_handler")
@pytest.mark.parametrize("allow_connection_errors", [True, False])
def test_allow_connection_errors(
    allow_connection_errors: bool,
    mock_requests: Mocker,
    warehouse_handler: WarehouseHandler,
    logger: Logger,
) -> None:
    """Test that the allow_connection_errors property works correctly."""

    mock_requests.reset_mock()

    mock_requests.get(
        REQUESTS_MOCK_ANY,
        exc=RequestsConnectionError(connection_str := "Connection Error: ¯\\_(ツ)_/¯"),
    )

    mock_requests.post(
        REQUESTS_MOCK_ANY,
        exc=RequestException(request_exc_str := "Request Exception: ︵(ಥ_ಥ)︵"),
    )

    if allow_connection_errors:
        wh_handler = WarehouseHandler(allow_connection_errors=allow_connection_errors)

        assert wh_handler._allow_connection_errors is allow_connection_errors

        warehouse_handler._allow_connection_errors = allow_connection_errors

        logger.info("Info log")
    else:
        with pytest.raises(RequestsConnectionError) as conn_exc_info:
            _ = WarehouseHandler(allow_connection_errors=allow_connection_errors)

        assert str(conn_exc_info.value) == connection_str

        warehouse_handler._allow_connection_errors = allow_connection_errors

        with pytest.raises(RequestException) as req_exc_info:
            logger.error("Info log")

        assert str(req_exc_info.value) == request_exc_str


@freeze_time("2021-01-01 00:00:00")
@pytest.mark.add_handler("warehouse_handler")
def test_pyscript_task_executor(
    logger: Logger, warehouse_handler: WarehouseHandler
) -> None:
    """Test that the pyscript_task_executor works correctly."""

    async def _pyscript_task_executor(
        func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        return func(*args, **kwargs)

    mock_task_executor = Mock(wraps=_pyscript_task_executor)

    warehouse_handler._pyscript_task_executor = mock_task_executor

    logger.debug("Debug log")
    logger.info("Info log")
    logger.warning("Warning log")
    logger.error("Error log")
    logger.critical("Critical log")

    assert mock_task_executor.call_args_list == [
        call(
            warehouse_handler.post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 10,
                "line": ANY,
                "log_hash": md5(
                    b"Debug log",
                ).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Debug log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            warehouse_handler.post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 20,
                "line": ANY,
                "log_hash": md5(
                    b"Info log",
                ).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Info log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            warehouse_handler.post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 30,
                "line": ANY,
                "log_hash": md5(
                    b"Warning log",
                ).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Warning log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            warehouse_handler.post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 40,
                "line": ANY,
                "log_hash": md5(
                    b"Error log",
                ).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Error log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
        call(
            warehouse_handler.post_json_response,
            "/warehouses/lumberyard/items",
            params=None,
            header_overrides=None,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "file": __file__,
                "level": 50,
                "line": ANY,
                "log_hash": md5(
                    b"Critical log",
                ).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Critical log",
                "module": "test__warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
            data=None,
        ),
    ]

    mock_task_executor.reset_mock()


def test_run_pyscript_task_executor_not_implemented(
    warehouse_handler: WarehouseHandler,
) -> None:
    """Test that `_run_pyscript_task_executor` raises a NotImplementedError."""

    assert warehouse_handler._pyscript_task_executor is None

    with pytest.raises(NotImplementedError) as exc_info:
        warehouse_handler._run_pyscript_task_executor(lambda: None)

    assert str(exc_info.value) == "Pyscript task executor is not defined"


@pytest.mark.add_handler("warehouse_handler")
@pytest.mark.asyncio()
async def test_emit_inside_event_loop(
    logger: Logger, mock_requests: Mocker, warehouse_handler: WarehouseHandler
) -> None:
    """Test that the emit method works correctly when called inside an event loop."""

    async def _pyscript_task_executor(
        func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        return func(*args, **kwargs)

    mock_task_executor = AsyncMock(side_effect=_pyscript_task_executor)

    warehouse_handler._pyscript_task_executor = mock_task_executor

    with patch(
        "wg_utilities.loggers.warehouse_handler.get_running_loop",
    ) as mock_get_running_loop:
        mock_get_running_loop.is_running.return_value = True

        logger.error("test message")

    mock_get_running_loop.assert_called_once_with()
    mock_get_running_loop.return_value.is_running.assert_called_once_with()
    mock_get_running_loop.return_value.create_task.assert_called_once()

    assert iscoroutine(
        coro := mock_get_running_loop.return_value.create_task.call_args[0][0]
    )

    assert coro.cr_code == warehouse_handler._async_task_executor.__code__

    assert not mock_requests.request_history

    mock_task_executor.assert_not_awaited()

    await coro

    json_payload = {
        "created_at": ANY,
        "file": __file__,
        "level": ERROR,
        "line": ANY,
        "log_hash": md5(
            b"test message",
        ).hexdigest(),
        "log_host": gethostname(),
        "logger": logger.name,
        "message": "test message",
        "module": "test__warehouse_handler",
        "process": "MainProcess",
        "thread": "MainThread",
    }

    mock_task_executor.assert_awaited_once_with(
        warehouse_handler.post_json_response,
        "/warehouses/lumberyard/items",
        params=None,
        header_overrides=None,
        timeout=5,
        json=json_payload,
        data=None,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": "https://item-warehouse.com/v1/warehouses/lumberyard/items",
                "method": "POST",
                "headers": {},
                "json": json_payload,
            }
        ],
    )
