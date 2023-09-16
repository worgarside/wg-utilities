# pylint: disable=protected-access
"""Unit tests for the PyscriptWarehouseHandler class."""


from __future__ import annotations

from asyncio import iscoroutine
from collections.abc import Callable
from hashlib import md5
from http import HTTPStatus
from logging import ERROR, Logger, LogRecord
from socket import gethostname
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, call, patch

import pytest
from freezegun import freeze_time
from requests_mock import Mocker

from tests.conftest import assert_mock_requests_request_history
from tests.unit.loggers.conftest import (
    IWH_DOT_COM,
    SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL,
)
from wg_utilities.loggers import PyscriptWarehouseHandler
from wg_utilities.loggers.item_warehouse.pyscript_warehouse_handler import (
    _PyscriptTaskExecutorProtocol,
)


def test_instantiation(
    pyscript_task_executor: _PyscriptTaskExecutorProtocol[Any],
) -> None:
    """Test that the PyscriptWarehouseHandler class can be instantiated."""

    pwh_handler = PyscriptWarehouseHandler(
        pyscript_task_executor=pyscript_task_executor
    )

    assert isinstance(pwh_handler, PyscriptWarehouseHandler)
    assert pwh_handler._pyscript_task_executor == pyscript_task_executor


@pytest.mark.add_handler("pyscript_warehouse_handler")
@pytest.mark.parametrize(("level", "message"), SAMPLE_LOG_RECORD_MESSAGES_WITH_LEVEL)
def test_emit(level: int, message: str, logger: Logger) -> None:
    """Test that the emit method sends the correct payload to the warehouse."""

    with patch.object(
        PyscriptWarehouseHandler, "_run_pyscript_task_executor"
    ) as mock_run_pyscript_task_executor, patch.object(
        PyscriptWarehouseHandler, "get_log_payload"
    ) as mock_get_log_payload:
        logger.log(level, message)

    mock_get_log_payload.assert_called_once()

    assert isinstance(mock_get_log_payload.call_args[0][0], LogRecord)

    mock_run_pyscript_task_executor.assert_called_once_with(
        logger.handlers[0].post_json_response,  # type: ignore[attr-defined]
        PyscriptWarehouseHandler.ITEM_ENDPOINT,
        timeout=5,
        json=mock_get_log_payload.return_value,
    )


@pytest.mark.add_handler("pyscript_warehouse_handler")
def test_emit_duplicate_record(
    logger: Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the emit method doesn't throw an error for duplicate records."""

    caplog.set_level(ERROR)

    with patch.object(
        PyscriptWarehouseHandler, "post_json_response"
    ) as mock_post_json_response:
        mock_post_json_response.return_value.status_code = HTTPStatus.CONFLICT

        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")
        logger.info("Info log")

    assert mock_post_json_response.call_count == 6

    assert not caplog.text


@pytest.mark.add_handler("pyscript_warehouse_handler")
def test_emit_http_error(
    caplog: pytest.LogCaptureFixture, logger: Logger, mock_requests: Mocker
) -> None:
    """Test that the emit method logs other HTTP errors."""

    caplog.set_level(ERROR)

    mock_requests.post(
        f"{IWH_DOT_COM}/v1/warehouses/lumberyard/items",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        reason=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
    )

    logger.info("Info log")

    assert (
        caplog.records[0].message
        == "Error logging to Item Warehouse: HTTPError('500 Server Error: "
        f"Internal Server Error for url: {IWH_DOT_COM}/v1/warehouses/lumberyard/items')"
    )


@freeze_time("2021-01-01 00:00:00")
@pytest.mark.add_handler("pyscript_warehouse_handler")
def test_pyscript_task_executor(
    logger: Logger, pyscript_warehouse_handler: PyscriptWarehouseHandler
) -> None:
    """Test that the pyscript_task_executor works correctly."""

    async def _pyscript_task_executor(
        func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        return func(*args, **kwargs)

    mock_task_executor = Mock(wraps=_pyscript_task_executor)

    pyscript_warehouse_handler._pyscript_task_executor = mock_task_executor

    logger.debug("Debug log")
    logger.info("Info log")
    logger.warning("Warning log")
    logger.error("Error log")
    logger.critical("Critical log")

    assert mock_task_executor.call_args_list == [
        call(
            pyscript_warehouse_handler.post_json_response,
            PyscriptWarehouseHandler.ITEM_ENDPOINT,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "exception_message": None,
                "exception_type": None,
                "exception_traceback": None,
                "file": __file__,
                "level": 10,
                "line": ANY,
                "log_hash": md5(b"Debug log", usedforsecurity=False).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Debug log",
                "module": "test__pyscript_warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
        ),
        call(
            pyscript_warehouse_handler.post_json_response,
            PyscriptWarehouseHandler.ITEM_ENDPOINT,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "exception_message": None,
                "exception_type": None,
                "exception_traceback": None,
                "file": __file__,
                "level": 20,
                "line": ANY,
                "log_hash": md5(b"Info log", usedforsecurity=False).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Info log",
                "module": "test__pyscript_warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
        ),
        call(
            pyscript_warehouse_handler.post_json_response,
            PyscriptWarehouseHandler.ITEM_ENDPOINT,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "exception_message": None,
                "exception_type": None,
                "exception_traceback": None,
                "file": __file__,
                "level": 30,
                "line": ANY,
                "log_hash": md5(b"Warning log", usedforsecurity=False).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Warning log",
                "module": "test__pyscript_warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
        ),
        call(
            pyscript_warehouse_handler.post_json_response,
            PyscriptWarehouseHandler.ITEM_ENDPOINT,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "exception_message": None,
                "exception_type": None,
                "exception_traceback": None,
                "file": __file__,
                "level": 40,
                "line": ANY,
                "log_hash": md5(b"Error log", usedforsecurity=False).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Error log",
                "module": "test__pyscript_warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
        ),
        call(
            pyscript_warehouse_handler.post_json_response,
            PyscriptWarehouseHandler.ITEM_ENDPOINT,
            timeout=5,
            json={
                "created_at": 1609459200.0,
                "exception_message": None,
                "exception_type": None,
                "exception_traceback": None,
                "file": __file__,
                "level": 50,
                "line": ANY,
                "log_hash": md5(b"Critical log", usedforsecurity=False).hexdigest(),
                "log_host": gethostname(),
                "logger": logger.name,
                "message": "Critical log",
                "module": "test__pyscript_warehouse_handler",
                "process": "MainProcess",
                "thread": "MainThread",
            },
        ),
    ]

    mock_task_executor.reset_mock()


@pytest.mark.add_handler("pyscript_warehouse_handler")
@pytest.mark.asyncio()
async def test_emit_inside_event_loop(
    logger: Logger,
    mock_requests: Mocker,
    pyscript_warehouse_handler: PyscriptWarehouseHandler,
) -> None:
    """Test that the emit method works correctly when called inside an event loop."""

    async def _pyscript_task_executor(
        func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        return func(*args, **kwargs)

    mock_task_executor = AsyncMock(side_effect=_pyscript_task_executor)

    pyscript_warehouse_handler._pyscript_task_executor = mock_task_executor

    with patch(
        "wg_utilities.loggers.item_warehouse.pyscript_warehouse_handler.get_running_loop",
    ) as mock_get_running_loop:
        mock_get_running_loop.is_running.return_value = True

        logger.error("test message")

    mock_get_running_loop.assert_called_once_with()
    mock_get_running_loop.return_value.is_running.assert_called_once_with()
    mock_get_running_loop.return_value.create_task.assert_called_once()

    assert iscoroutine(
        coro := mock_get_running_loop.return_value.create_task.call_args[0][0]
    )

    assert coro.cr_code == pyscript_warehouse_handler._async_task_executor.__code__

    assert not mock_requests.request_history

    mock_task_executor.assert_not_awaited()

    await coro

    json_payload = {
        "created_at": ANY,
        "exception_message": None,
        "exception_type": None,
        "exception_traceback": None,
        "file": __file__,
        "level": ERROR,
        "line": ANY,
        "log_hash": md5(b"test message", usedforsecurity=False).hexdigest(),
        "log_host": gethostname(),
        "logger": logger.name,
        "message": "test message",
        "module": "test__pyscript_warehouse_handler",
        "process": "MainProcess",
        "thread": "MainThread",
    }

    mock_task_executor.assert_awaited_once_with(
        pyscript_warehouse_handler.post_json_response,
        PyscriptWarehouseHandler.ITEM_ENDPOINT,
        timeout=5,
        json=json_payload,
    )

    assert_mock_requests_request_history(
        mock_requests.request_history,
        [
            {
                "url": f"{IWH_DOT_COM}/v1/warehouses/lumberyard/items",
                "method": "POST",
                "headers": {},
                "json": json_payload,
            }
        ],
    )
