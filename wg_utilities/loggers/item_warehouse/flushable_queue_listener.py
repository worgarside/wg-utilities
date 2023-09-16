"""Simple subclass of logging.handlers.QueueListener that can be flushed and stopped."""

from __future__ import annotations

from logging import getLogger
from logging.handlers import QueueListener
from multiprocessing import Queue
from time import sleep, time
from typing import Any

LOGGER = getLogger(__name__)


class FlushableQueueListener(QueueListener):
    """A QueueListener that can be flushed and stopped."""

    queue: Queue[Any]  # pylint: disable=unsubscriptable-object

    def flush_and_stop(self, timeout: float = 300) -> None:
        """Wait for the queue to empty and stop.

        Args:
            timeout (float): the maximum time to wait for the queue to empty
        """

        start_time = time()

        while not self.queue.empty():
            sleep(1)

            if 0 < timeout < time() - start_time:
                LOGGER.warning(
                    "QueueListener failed to flush after %s seconds", timeout
                )
                break

        self.stop()
