# ruff: noqa
"""Config for the EPD.

* | File        :	  epdconfig.py
* | Author      :   Waveshare team
* | Function    :   Hardware underlying interface
* | Info        :
*----------------
* | This version:   V1.0
* | Date        :   2019-06-21
* | Info        :
******************************************************************************
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS OR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from __future__ import annotations


from logging import debug, exception
from os import path
from sys import modules
from time import sleep
from typing import Literal


# noinspection PyMissingOrEmptyDocstring
class RaspberryPi:
    # Pin definition
    RST_PIN = 17
    DC_PIN = 25
    CS_PIN = 8
    BUSY_PIN = 24

    # noinspection PyUnresolvedReferences,PyPackageRequirements

    def __init__(self) -> None:
        from RPi import GPIO  # type: ignore[import-not-found]
        from spidev import SpiDev  # type: ignore[import-not-found]

        self.gpio = GPIO

        # SPI device, bus = 0, device = 0
        self.spi = SpiDev(0, 0)

    def digital_write(self, pin: int, value: bool) -> None:
        self.gpio.output(pin, value)

    def digital_read(self, pin: int) -> bool:
        return self.gpio.input(pin)  # type: ignore[no-any-return]

    @staticmethod
    def delay_ms(delay_time: float | int) -> None:
        sleep(delay_time / 1000.0)

    def spi_writebyte(self, data: list[int]) -> None:
        self.spi.writebytes(data)

    # noinspection DuplicatedCode
    def module_init(self) -> Literal[0]:
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setwarnings(False)
        self.gpio.setup(self.RST_PIN, self.gpio.OUT)
        self.gpio.setup(self.DC_PIN, self.gpio.OUT)
        self.gpio.setup(self.CS_PIN, self.gpio.OUT)
        self.gpio.setup(self.BUSY_PIN, self.gpio.IN)
        self.spi.max_speed_hz = 4000000
        self.spi.mode = 0b00
        return 0

    def module_exit(self) -> None:
        debug("spi end")
        self.spi.close()

        debug("close 5V, Module enters 0 power consumption ...")
        self.gpio.output(self.RST_PIN, 0)
        self.gpio.output(self.DC_PIN, 0)

        self.gpio.cleanup()


try:
    if path.exists("/sys/bus/platform/drivers/gpiomem-bcm2835"):
        implementation: RaspberryPi | FakeImplementation = RaspberryPi()
    else:
        raise RuntimeError("Unsupported platform (Jetson Nano?)")

    for func in dir(implementation):
        if not func.startswith("_"):
            setattr(modules[__name__], func, getattr(implementation, func))

    TEST_MODE = False
except (RuntimeError, ImportError) as exc:
    exception(exc)

    class FakeImplementation:
        """Class to cover functionality of implementations on non-supporting devices."""

    for method in dir(RaspberryPi):
        if not method.startswith("_"):
            setattr(FakeImplementation, method, lambda *_, **__: None)

    implementation = FakeImplementation()

    TEST_MODE = True
