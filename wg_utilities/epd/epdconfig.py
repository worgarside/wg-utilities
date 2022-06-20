# type: ignore
"""
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
# pylint: disable=missing-function-docstring,missing-class-docstring

from logging import debug
from os import path
from os.path import dirname, exists, join, realpath
from sys import modules
from time import sleep


# noinspection PyMissingOrEmptyDocstring
class RaspberryPi:
    # Pin definition
    RST_PIN = 17
    DC_PIN = 25
    CS_PIN = 8
    BUSY_PIN = 24

    # noinspection PyUnresolvedReferences,PyPackageRequirements
    # pylint: disable=import-outside-toplevel
    def __init__(self):
        from RPi import GPIO
        from spidev import SpiDev

        self.gpio = GPIO

        # SPI device, bus = 0, device = 0
        self.spi = SpiDev(0, 0)

    def digital_write(self, pin, value):
        self.gpio.output(pin, value)

    def digital_read(self, pin):
        return self.gpio.input(pin)

    @staticmethod
    def delay_ms(delay_time):
        sleep(delay_time / 1000.0)

    def spi_writebyte(self, data):
        self.spi.writebytes(data)

    # noinspection DuplicatedCode
    def module_init(self):
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setwarnings(False)
        self.gpio.setup(self.RST_PIN, self.gpio.OUT)
        self.gpio.setup(self.DC_PIN, self.gpio.OUT)
        self.gpio.setup(self.CS_PIN, self.gpio.OUT)
        self.gpio.setup(self.BUSY_PIN, self.gpio.IN)
        self.spi.max_speed_hz = 4000000
        self.spi.mode = 0b00
        return 0

    def module_exit(self):
        debug("spi end")
        self.spi.close()

        debug("close 5V, Module enters 0 power consumption ...")
        self.gpio.output(self.RST_PIN, 0)
        self.gpio.output(self.DC_PIN, 0)

        self.gpio.cleanup()


# noinspection PyMissingOrEmptyDocstring
class JetsonNano:
    # Pin definition
    RST_PIN = 17
    DC_PIN = 25
    CS_PIN = 8
    BUSY_PIN = 24

    # noinspection PyUnresolvedReferences
    # pylint: disable=import-outside-toplevel
    def __init__(self):
        from ctypes.cdll import LoadLibrary

        from Jetson import GPIO

        self.spi = None

        for find_dir in [
            dirname(realpath(__file__)),
            "/usr/local/lib",
            "/usr/lib",
        ]:
            so_filename = join(find_dir, "sysfs_software_spi.so")
            if exists(so_filename):
                self.spi = LoadLibrary(so_filename)
                break

        if self.spi is None:
            raise RuntimeError("Cannot find sysfs_software_spi.so")

        self.gpio = GPIO

    def digital_write(self, pin, value):
        self.gpio.output(pin, value)

    def digital_read(self, _):
        return self.gpio.input(self.BUSY_PIN)

    @staticmethod
    def delay_ms(delay_time):
        sleep(delay_time / 1000.0)

    def spi_writebyte(self, data):
        self.spi.SYSFS_software_spi_transfer(data[0])

    # noinspection DuplicatedCode
    def module_init(self):
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setwarnings(False)
        self.gpio.setup(self.RST_PIN, self.gpio.OUT)
        self.gpio.setup(self.DC_PIN, self.gpio.OUT)
        self.gpio.setup(self.CS_PIN, self.gpio.OUT)
        self.gpio.setup(self.BUSY_PIN, self.gpio.IN)
        self.spi.SYSFS_software_spi_begin()
        return 0

    def module_exit(self):
        debug("spi end")
        self.spi.SYSFS_software_spi_end()

        debug("close 5V, Module enters 0 power consumption ...")
        self.gpio.output(self.RST_PIN, 0)
        self.gpio.output(self.DC_PIN, 0)

        self.gpio.cleanup()


try:
    if path.exists("/sys/bus/platform/drivers/gpiomem-bcm2835"):
        implementation = RaspberryPi()
    else:
        implementation = JetsonNano()

    for func in dir(implementation):
        if not func.startswith("_"):
            setattr(modules[__name__], func, getattr(implementation, func))

    TEST_MODE = False
except (RuntimeError, ImportError):

    # pylint: disable=too-few-public-methods
    class FakeImplementation:
        """Class to cover functionality of implementations on non-supporting devices"""

    for method in set().union(dir(RaspberryPi), dir(JetsonNano)):
        if not method.startswith("_"):
            setattr(FakeImplementation, method, lambda *a, **k: None)

    implementation = FakeImplementation()

    TEST_MODE = True
