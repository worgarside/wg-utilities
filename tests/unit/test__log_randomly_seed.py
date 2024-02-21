"""A single "test" which is used to log the `pytest-randomly` seed."""

from __future__ import annotations

from logging import INFO, getLogger
from typing import TYPE_CHECKING

from wg_utilities.loggers import add_stream_handler

if TYPE_CHECKING:
    import pytest

_LOGGER = getLogger(__name__)
_LOGGER.setLevel(INFO)
add_stream_handler(_LOGGER)


def test_randomly_seed(request: pytest.FixtureRequest) -> None:
    """Ensure the randomly seed is always logged."""

    _LOGGER.info("Randomly seed: %s", request.config.getoption("--randomly-seed"))
