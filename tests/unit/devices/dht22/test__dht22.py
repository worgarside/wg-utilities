"""Unit Tests for the `wg_utilities.devices.dht22.dht22_lib.DHT22Sensor` class."""
from __future__ import annotations

from unittest.mock import MagicMock, call

from pigpio import _callback  # type: ignore[import]

from wg_utilities.devices.dht22 import DHT22Sensor


def test_instantiation(pigpio_pi: MagicMock) -> None:
    """Test that the class can be instantiated."""
    dht22_sensor = DHT22Sensor(pi_obj=pigpio_pi, gpio=4)

    pigpio_pi.set_pull_up_down.assert_called_once_with(4, 0)
    assert pigpio_pi.set_pull_up_down.set_watchdog(4, 0)

    assert isinstance(dht22_sensor, DHT22Sensor)
    assert dht22_sensor.gpio == 4
    assert dht22_sensor.led is None
    assert dht22_sensor.power is None
    assert dht22_sensor.powered is True


def test_trigger_method(dht22_sensor: DHT22Sensor, pigpio_pi: MagicMock) -> None:
    """Test that the trigger method works."""
    dht22_sensor.trigger()

    pigpio_pi.write.assert_called_once_with(4, 0)
    pigpio_pi.set_mode.assert_called_once_with(4, 0)
    pigpio_pi.set_watchdog.assert_called_with(4, 200)


def test_trigger_method_led_is_not_none(
    dht22_sensor: DHT22Sensor, pigpio_pi: MagicMock
) -> None:
    """Test that the trigger method updates the LED pin when a value is set."""
    dht22_sensor.led = 5
    dht22_sensor.trigger()

    assert pigpio_pi.write.call_args_list == [
        call(5, 1),
        call(4, 0),
    ]
    pigpio_pi.set_mode.assert_called_once_with(4, 0)
    pigpio_pi.set_watchdog.assert_called_with(4, 200)


def test_cancel_method(dht22_sensor: DHT22Sensor, pigpio_pi: MagicMock) -> None:
    """Test that the trigger method works."""
    assert isinstance(dht22_sensor.callback, _callback)

    dht22_sensor.cancel()

    pigpio_pi.set_watchdog.assert_called_with(4, 0)
    assert dht22_sensor.callback is None

    pigpio_pi.reset_mock()

    dht22_sensor.cancel()

    pigpio_pi.set_watchdog.assert_called_once_with(4, 0)
    # Shouldn't be called as the previous
    assert pigpio_pi.callback.cancel.call_count == 0
