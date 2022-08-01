"""A class I found a long time ago for DHT22, I can't remember where :("""
from __future__ import annotations

from time import sleep

from pigpio import EITHER_EDGE, INPUT, LOW, PUD_OFF, pi, tickDiff


class DHT22Sensor:
    """Class for DHT22 sensor, I can't remember where I got this from!

    Args:
        pi_obj (pi): a PI instance from pigpio
        gpio (int): the DHT22's data pin(?)
        led (int): an optional LED pin?
        power (int): an optional power pin, not sure what for though
    """

    MAX_NO_RESPONSE = 2

    def __init__(
        self,
        pi_obj: pi,
        gpio: int,
        led: int | None = None,
        power: int | None = None,
    ):
        self.pi = pi_obj
        self.gpio = gpio
        self.led = led
        self.power = power

        if self.power is not None:
            self.pi.write(self.power, 1)  # Switch Sensor on.
            sleep(2)

        self.powered = True

        self.callback = None

        self.bad_cs = 0  # Bad checksum count.
        self.bad_sm = 0  # Short message count.
        self.bad_mm = 0  # Missing message count.
        self.bad_sr = 0  # Sensor reset count.

        # Power cycle if timeout > MAX_TIMEOUTS.
        self.no_response = 0

        self.humidity: float = -999
        self.temperature: float = -999

        self.high_tick = 0
        self.bit = 40

        self.pi.set_pull_up_down(self.gpio, PUD_OFF)

        self.pi.set_watchdog(self.gpio, 0)  # Kill any watchdogs.

        self.callback = self.pi.callback(self.gpio, EITHER_EDGE, self._cb)

        self.hum_high: int  # humidity high byte
        self.hum_low: int  # humidity low byte
        self.temp_high: int  # temp high byte
        self.temp_low: int  # temp low byte
        self.checksum: int  # checksum

    def _cb(self, _: int, level: int, tick: int) -> None:
        # pylint: disable=too-many-branches,too-many-statements
        """
        Accumulate the 40 data bits.  Format into 5 bytes, humidity high,
        humidity low, temperature high, temperature low, checksum.

        Args:
            _ (int):        0-31    The GPIO which has changed state
            level (int):    0-2     0 = change to low (a falling edge)
                                    1 = change to high (a rising edge)
                                    2 = no level change (a watchdog timeout)
            tick (int):    32 bit   The number of microseconds since boot
                                    WARNING: this wraps around from
                                    4294967295 to 0 roughly every 72 minutes
        """

        diff = tickDiff(self.high_tick, tick)

        if level == 0:

            # Edge length determines if bit is 1 or 0.
            if diff >= 50:
                val = 1
                if diff >= 200:  # Bad bit?
                    self.checksum = 256  # Force bad checksum.
            else:
                val = 0

            if self.bit >= 40:  # Message complete.
                self.bit = 40

            elif self.bit >= 32:  # In checksum byte.
                self.checksum = (self.checksum << 1) + val

                if self.bit == 39:

                    # 40th bit received.

                    self.pi.set_watchdog(self.gpio, 0)

                    self.no_response = 0

                    total = (
                        self.hum_high + self.hum_low + self.temp_high + self.temp_low
                    )

                    if (total & 255) == self.checksum:  # Is checksum ok?

                        self.humidity = ((self.hum_high << 8) + self.hum_low) * 0.1

                        if self.temp_high & 128:  # Negative temperature.
                            mult = -0.1
                            self.temp_high &= 127
                        else:
                            mult = 0.1

                        self.temperature = (
                            (self.temp_high << 8) + self.temp_low
                        ) * mult

                        if self.led is not None:
                            self.pi.write(self.led, 0)

                    else:

                        self.bad_cs += 1

            elif self.bit >= 24:  # in temp low byte
                self.temp_low = (self.temp_low << 1) + val

            elif self.bit >= 16:  # in temp high byte
                self.temp_high = (self.temp_high << 1) + val

            elif self.bit >= 8:  # in humidity low byte
                self.hum_low = (self.hum_low << 1) + val

            elif self.bit >= 0:  # in humidity high byte
                self.hum_high = (self.hum_high << 1) + val

            else:  # header bits
                pass

            self.bit += 1

        elif level == 1:
            self.high_tick = tick
            if diff > 250000:
                self.bit = -2
                self.hum_high = 0
                self.hum_low = 0
                self.temp_high = 0
                self.temp_low = 0
                self.checksum = 0

        else:  # level == pigpio.TIMEOUT:
            self.pi.set_watchdog(self.gpio, 0)
            if self.bit < 8:  # Too few data bits received.
                self.bad_mm += 1  # Bump missing message count.
                self.no_response += 1
                if self.no_response > self.MAX_NO_RESPONSE:
                    self.no_response = 0
                    self.bad_sr += 1  # Bump Sensor reset count.
                    if self.power is not None:
                        self.powered = False
                        self.pi.write(self.power, 0)
                        sleep(2)
                        self.pi.write(self.power, 1)
                        sleep(2)
                        self.powered = True
            elif self.bit < 39:  # Short message received.
                self.bad_sm += 1  # Bump short message count.
                self.no_response = 0

            else:  # Full message received.
                self.no_response = 0

    def trigger(self) -> None:
        """Trigger a new relative humidity and temperature reading."""
        if self.powered:
            if self.led is not None:
                self.pi.write(self.led, 1)

            self.pi.write(self.gpio, LOW)
            sleep(0.017)  # 17 ms
            self.pi.set_mode(self.gpio, INPUT)
            self.pi.set_watchdog(self.gpio, 200)

    def cancel(self) -> None:
        """Cancel the DHT22 Sensor."""

        self.pi.set_watchdog(self.gpio, 0)

        if self.callback is not None:
            self.callback.cancel()
            self.callback = None
