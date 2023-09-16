"""Unit Tests for the `add_pyscript_warehouse_handler` function."""
from __future__ import annotations

from http import HTTPStatus
from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARN, WARNING, Logger
from socket import gethostname
from typing import Any

import pytest
from requests_mock import Mocker

from tests.unit.loggers.conftest import IWH_DOT_COM, WAREHOUSE_SCHEMA
from wg_utilities.loggers import (
    PyscriptWarehouseHandler,
    add_pyscript_warehouse_handler,
)
from wg_utilities.loggers.item_warehouse.pyscript_warehouse_handler import (
    _PyscriptTaskExecutorProtocol,
)


def test_handler_is_applied_to_logger_correctly(
    logger: Logger, pyscript_task_executor: _PyscriptTaskExecutorProtocol[Any]
) -> None:
    """Test that the handler is applied to the logger correctly."""

    add_pyscript_warehouse_handler(
        logger,
        warehouse_host=IWH_DOT_COM,
        warehouse_port=0,
        pyscript_task_executor=pyscript_task_executor,
    )

    assert len(logger.handlers) == 1

    pwh_handler = logger.handlers[0]

    assert isinstance(pwh_handler, PyscriptWarehouseHandler)

    assert gethostname() == pwh_handler.HOST_NAME
    assert pwh_handler.ITEM_NAME == "log"
    assert pwh_handler.WAREHOUSE_NAME == "lumberyard"
    assert pwh_handler.WAREHOUSE_ENDPOINT == "/warehouses/lumberyard"


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
def test_log_level_is_set_correctly(
    level: int,
    logger: Logger,
    pyscript_task_executor: _PyscriptTaskExecutorProtocol[Any],
) -> None:
    """Test that the log level is set correctly."""

    add_pyscript_warehouse_handler(
        logger,
        level=level,
        warehouse_host=IWH_DOT_COM,
        pyscript_task_executor=pyscript_task_executor,
    )

    assert len(logger.handlers) == 1

    pwh_handler = logger.handlers[0]

    assert isinstance(pwh_handler, PyscriptWarehouseHandler)
    assert pwh_handler.level == level


def test_handler_only_added_once(
    logger: Logger,
    caplog: pytest.LogCaptureFixture,
    mock_requests: Mocker,
    pyscript_task_executor: _PyscriptTaskExecutorProtocol[Any],
) -> None:
    """Test that a PyscriptWarehouseHandler can only be added to a Logger once."""

    caplog.set_level(WARNING)

    assert len(logger.handlers) == 0

    pwh_handler = add_pyscript_warehouse_handler(
        logger,
        warehouse_host=IWH_DOT_COM,
        pyscript_task_executor=pyscript_task_executor,
    )

    assert len(logger.handlers) == 1

    assert (
        add_pyscript_warehouse_handler(
            logger,
            warehouse_host=IWH_DOT_COM,
            pyscript_task_executor=pyscript_task_executor,
        )
        == pwh_handler
    )

    for level in (CRITICAL, FATAL, ERROR, WARNING, WARN, INFO, DEBUG, NOTSET):
        assert (
            add_pyscript_warehouse_handler(
                logger,
                warehouse_host=IWH_DOT_COM,
                level=level,
                pyscript_task_executor=pyscript_task_executor,
            )
            == pwh_handler
        )

    assert len(logger.handlers) == 1

    assert caplog.records[0].levelno == WARNING
    assert (
        caplog.records[0].getMessage()
        == f"PyscriptWarehouseHandler already exists for {pwh_handler.base_url}"
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
        add_pyscript_warehouse_handler(
            logger,
            warehouse_host="https://a-different-host.com",
            pyscript_task_executor=pyscript_task_executor,
        )
        != pwh_handler
    )

    assert len(logger.handlers) == 2
