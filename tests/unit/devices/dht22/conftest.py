"""Fixtures for DHT22 sensor tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pigpio import _callback  # type: ignore[import]

from tests.conftest import YieldFixture
from wg_utilities.devices.dht22 import DHT22Sensor


@pytest.fixture(name="dht22_sensor")
def dht22_sensor_(pigpio_pi: MagicMock) -> DHT22Sensor:
    """Fixture for DHT22 sensor."""

    return DHT22Sensor(pigpio_pi, gpio=4)


@pytest.fixture(name="pigpio_pi")
def pigpio_pi_() -> YieldFixture[MagicMock]:
    """Fixture for creating a `pigpio.pi` instance."""

    pi = MagicMock()

    pi.INPUT = 0
    pi.OUTPUT = 1

    pi.callback.return_value = _callback(MagicMock(), 4)

    return pi
