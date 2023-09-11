# pylint: disable=protected-access
"""Unit Tests for the `add_warehouse_handler` function."""
from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus
from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARN, WARNING, Logger
from socket import gethostname
from typing import Any

import pytest
from requests_mock import Mocker

from tests.unit.loggers.conftest import WAREHOUSE_SCHEMA
from wg_utilities.loggers.warehouse_handler import (
    WarehouseHandler,
    add_warehouse_handler,
)


def test_handler_is_applied_to_logger_correctly(logger: Logger) -> None:
    """Test that the handler is applied to the logger correctly."""

    async def _pyscript_task_executor(
        func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        return func(*args, **kwargs)

    add_warehouse_handler(
        logger,
        warehouse_host="https://item-warehouse.com",
        allow_connection_errors=False,
        pyscript_task_executor=_pyscript_task_executor,
    )

    assert len(logger.handlers) == 1

    wh_handler = logger.handlers[0]

    assert isinstance(wh_handler, WarehouseHandler)

    assert gethostname() == wh_handler.HOST_NAME
    assert wh_handler.ITEM_NAME == "log"
    assert wh_handler.WAREHOUSE_NAME == "lumberyard"
    assert wh_handler.WAREHOUSE_ENDPOINT == "/warehouses/lumberyard"
    assert wh_handler._allow_connection_errors is False
    assert wh_handler._pyscript_task_executor is _pyscript_task_executor  # type: ignore[comparison-overlap]


@pytest.mark.parametrize(
    "level",
    [
        CRITICAL,
        FATAL,
        ERROR,
        WARNING,
        WARN,
        INFO,
        DEBUG,
        NOTSET,
    ],
)
def test_log_level_is_set_correctly(level: int, logger: Logger) -> None:
    """Test that the log level is set correctly."""

    add_warehouse_handler(
        logger, level=level, warehouse_host="https://item-warehouse.com"
    )

    assert len(logger.handlers) == 1

    wh_handler = logger.handlers[0]

    assert isinstance(wh_handler, WarehouseHandler)
    assert wh_handler.level == level


def test_handler_only_added_once(
    logger: Logger, caplog: pytest.LogCaptureFixture, mock_requests: Mocker
) -> None:
    """Test that a WarehouseHandler can only be added to a Logger once."""

    caplog.set_level(WARNING)

    assert len(logger.handlers) == 0

    wh_handler = add_warehouse_handler(
        logger,
        warehouse_host="https://item-warehouse.com",
        allow_connection_errors=False,
    )

    assert len(logger.handlers) == 1

    assert (
        add_warehouse_handler(
            logger,
            warehouse_host="https://item-warehouse.com",
            allow_connection_errors=False,
        )
        == wh_handler
    )

    for level in (CRITICAL, FATAL, ERROR, WARNING, WARN, INFO, DEBUG, NOTSET):
        assert (
            add_warehouse_handler(
                logger,
                warehouse_host="https://item-warehouse.com",
                allow_connection_errors=False,
                level=level,
            )
            == wh_handler
        )

    assert len(logger.handlers) == 1

    assert caplog.records[0].levelno == WARNING
    assert (
        caplog.records[0].getMessage()
        == f"WarehouseHandler already exists for {wh_handler.base_url}"
    )

    mock_requests.get(
        "/".join(
            [
                "https://a-different-host.com",
                "v1",
                "warehouses",
                "lumberyard",
            ]
        ),
        status_code=HTTPStatus.OK,
        reason=HTTPStatus.OK.phrase,
        json=WAREHOUSE_SCHEMA,
    )

    assert (
        add_warehouse_handler(
            logger,
            warehouse_host="https://a-different-host.com",
            allow_connection_errors=False,
        )
        != wh_handler
    )

    assert len(logger.handlers) == 2
