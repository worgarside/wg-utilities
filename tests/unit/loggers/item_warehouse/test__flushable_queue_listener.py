"""Unit tests for the FlushableQueueListener class."""

from __future__ import annotations

from logging import NullHandler
from random import choice
from time import sleep
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.loggers.conftest import SAMPLE_LOG_RECORDS
from wg_utilities.loggers.item_warehouse.flushable_queue_listener import (
    FlushableQueueListener,
)


def test_flush_and_stop() -> None:
    """Test the flush_and_stop method of the FlushableQueueListener class."""

    log_queue = MagicMock()

    empty_call_count = 0

    def _empty_side_effect() -> bool:
        nonlocal empty_call_count

        empty_call_count += 1

        return empty_call_count > 5

    log_queue.empty.side_effect = _empty_side_effect
    log_queue.get.side_effect = lambda _: choice(SAMPLE_LOG_RECORDS)

    listener = FlushableQueueListener(log_queue, NullHandler())

    with patch(
        "wg_utilities.loggers.item_warehouse.flushable_queue_listener.sleep",
    ) as mock_sleep, patch.object(listener, "stop") as mock_stop:
        listener.flush_and_stop()

    assert mock_sleep.call_count == 5

    mock_stop.assert_called_once_with()


def test_flush_and_stop_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the flush_and_stop exits cleanly when it times out."""

    log_queue = MagicMock()

    log_queue.empty.return_value = False
    log_queue.get.side_effect = lambda _: choice(SAMPLE_LOG_RECORDS)

    listener = FlushableQueueListener(log_queue, NullHandler())

    with patch(
        "wg_utilities.loggers.item_warehouse.flushable_queue_listener.sleep",
        wraps=sleep,
    ) as mock_sleep, patch.object(listener, "stop") as mock_stop:
        listener.flush_and_stop(timeout=2)

    assert mock_sleep.call_count == 2
    mock_stop.assert_called_once_with()

    assert "QueueListener failed to flush after 2 seconds" in caplog.text
