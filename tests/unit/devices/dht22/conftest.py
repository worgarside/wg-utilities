"""Fixtures for DHT22 sensor tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from pigpio import _callback  # type: ignore[import]
from pytest import fixture

from tests.conftest import YieldFixture
from wg_utilities.devices.dht22 import DHT22Sensor


@fixture(scope="function", name="dht22_sensor")
def _dht22_sensor(pigpio_pi: MagicMock) -> DHT22Sensor:
    """Fixture for DHT22 sensor."""

    return DHT22Sensor(pigpio_pi, 4)


@fixture(scope="function", name="pigpio_pi")
def _pigpio_pi() -> YieldFixture[MagicMock]:
    """Fixture for creating a `pigpio.pi` instance."""

    pi = MagicMock()

    pi.INPUT = 0
    pi.OUTPUT = 1

    pi.callback.return_value = _callback(MagicMock(), 4)

    return pi
