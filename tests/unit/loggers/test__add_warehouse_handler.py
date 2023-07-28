"""Unit Tests for the `add_warehouse_handler` function."""
from __future__ import annotations

from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, NOTSET, WARN, WARNING, Logger
from socket import gethostname

from pytest import mark

from wg_utilities.loggers import WarehouseHandler, add_warehouse_handler


def test_handler_is_applied_to_logger_correctly(logger: Logger) -> None:
    """Test that the handler is applied to the logger correctly."""

    add_warehouse_handler(logger)

    assert len(logger.handlers) == 1

    wh_handler = logger.handlers[0]

    assert isinstance(wh_handler, WarehouseHandler)

    assert wh_handler.HOST_NAME == gethostname()
    assert wh_handler.ITEM_NAME == "log"
    assert wh_handler.WAREHOUSE_NAME == "lumberyard"
    assert wh_handler.WAREHOUSE_ENDPOINT == "/warehouses/lumberyard"


@mark.parametrize(
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

    add_warehouse_handler(logger, level=level)

    assert len(logger.handlers) == 1

    wh_handler = logger.handlers[0]

    assert isinstance(wh_handler, WarehouseHandler)
    assert wh_handler.level == level
