"""Unit Tests for the `add_warehouse_handler` function."""

from __future__ import annotations

from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARNING, Logger
from logging.handlers import QueueHandler
from socket import gethostname
from unittest.mock import patch

import pytest

from tests.unit.loggers.conftest import IWH_DOT_COM
from wg_utilities.loggers import WarehouseHandler, add_warehouse_handler
from wg_utilities.loggers.item_warehouse.warehouse_handler import LOG_QUEUE


def test_vanilla_handler_is_applied_to_logger_correctly(
    logger: Logger,
) -> None:
    """Test that the handler is applied to the logger correctly."""

    add_warehouse_handler(logger, warehouse_host=IWH_DOT_COM, disable_queue=True)

    assert len(logger.handlers) == 1

    wh_handler = logger.handlers[0]

    assert isinstance(wh_handler, WarehouseHandler)

    assert gethostname() == wh_handler.HOST_NAME
    assert wh_handler.ITEM_NAME == "log"
    assert wh_handler.WAREHOUSE_NAME == "lumberyard"
    assert wh_handler.WAREHOUSE_ENDPOINT == "/warehouses/lumberyard"


def test_queue_handler_is_applied_to_logger_correctly(
    logger: Logger,
) -> None:
    """Test that the handler is applied to the logger correctly."""

    with patch(
        "wg_utilities.loggers.item_warehouse.warehouse_handler.FlushableQueueListener",
    ) as mock_flushable_queue_listener, patch(
        "wg_utilities.loggers.item_warehouse.warehouse_handler.atexit",
    ) as mock_atexit:
        wh_handler = add_warehouse_handler(
            logger,
            warehouse_host=IWH_DOT_COM,
            level=WARNING,
        )

    assert len(logger.handlers) == 1

    q_handler = logger.handlers[0]
    assert isinstance(q_handler, QueueHandler)
    assert q_handler.queue == LOG_QUEUE
    assert q_handler.level == WARNING

    mock_flushable_queue_listener.assert_called_once_with(
        LOG_QUEUE,
        wh_handler,
    )
    mock_flushable_queue_listener.return_value.start.assert_called_once_with()

    assert mock_atexit.register.call_count == 3


@pytest.mark.parametrize(
    ("level", "disable_queue"),
    [
        (level, flag)
        for level in [
            CRITICAL,
            FATAL,
            ERROR,
            WARNING,
            WARNING,
            INFO,
            DEBUG,
            NOTSET,
        ]
        for flag in [True, False]
    ],
)
def test_log_level_is_set_correctly(
    level: int,
    disable_queue: bool,
    logger: Logger,
) -> None:
    """Test that the log level is set correctly."""

    add_warehouse_handler(
        logger,
        level=level,
        warehouse_host=IWH_DOT_COM,
        disable_queue=disable_queue,
    )

    assert len(logger.handlers) == 1

    handler = logger.handlers[0]

    assert isinstance(handler, WarehouseHandler if disable_queue else QueueHandler)
    assert handler.level == level


@pytest.mark.parametrize(
    "disable_queue",
    [True, False],
)
def test_handler_only_added_once(
    logger: Logger,
    caplog: pytest.LogCaptureFixture,
    disable_queue: bool,
) -> None:
    """Test that a WarehouseHandler can only be added to a Logger once."""

    caplog.set_level(WARNING)

    assert len(logger.handlers) == 0

    wh_handler = add_warehouse_handler(
        logger,
        disable_queue=disable_queue,
    )

    assert len(logger.handlers) == 1

    assert (
        add_warehouse_handler(
            logger,
            disable_queue=disable_queue,
        )
        == wh_handler
    )

    assert len(logger.handlers) == 1

    assert caplog.records[0].levelno == WARNING
    assert (
        caplog.records[0].getMessage()
        == "WarehouseHandler already exists for http://homeassistant.local:8002/v1"
    )

    assert (
        add_warehouse_handler(
            logger,
            warehouse_host="https://a-different-host.com",
            warehouse_port=0,
            disable_queue=disable_queue,
        )
        != wh_handler
    )

    assert len(logger.handlers) == 2
