# ruff: noqa
"""EPD class.

* | File        :	  epd7in5.py
* | Author      :   Waveshare team
* | Function    :   Electronic paper driver
* | Info        :
*----------------
* | This version:   V4.0
* | Date        :   2019-06-20
# | Info        :   python demo
-----------------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to  whom the Software is
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


from logging import debug

from PIL.Image import Image

from wg_utilities.devices.epd import epdconfig

# Display resolution
EPD_WIDTH = 800
EPD_HEIGHT = 480


# noinspection PyUnresolvedReferences,PyMissingOrEmptyDocstring,SpellCheckingInspection
class EPD:
    def __init__(self) -> None:
        self.reset_pin = epdconfig.RST_PIN  # type: ignore[attr-defined]
        self.dc_pin = epdconfig.DC_PIN  # type: ignore[attr-defined]
        self.busy_pin = epdconfig.BUSY_PIN  # type: ignore[attr-defined]
        self.cs_pin = epdconfig.CS_PIN  # type: ignore[attr-defined]
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

    # Hardware reset
    def reset(self) -> None:
        epdconfig.digital_write(self.reset_pin, 1)  # type: ignore[attr-defined]
        epdconfig.delay_ms(200)  # type: ignore[attr-defined]
        epdconfig.digital_write(self.reset_pin, 0)  # type: ignore[attr-defined]
        epdconfig.delay_ms(2)  # type: ignore[attr-defined]
        epdconfig.digital_write(self.reset_pin, 1)  # type: ignore[attr-defined]
        epdconfig.delay_ms(200)  # type: ignore[attr-defined]

    def send_command(self, command: int) -> None:
        epdconfig.digital_write(self.dc_pin, 0)  # type: ignore[attr-defined]
        epdconfig.digital_write(self.cs_pin, 0)  # type: ignore[attr-defined]
        epdconfig.spi_writebyte([command])  # type: ignore[attr-defined]
        epdconfig.digital_write(self.cs_pin, 1)  # type: ignore[attr-defined]

    def send_data(self, data: int) -> None:
        epdconfig.digital_write(self.dc_pin, 1)  # type: ignore[attr-defined]
        epdconfig.digital_write(self.cs_pin, 0)  # type: ignore[attr-defined]
        epdconfig.spi_writebyte([data])  # type: ignore[attr-defined]
        epdconfig.digital_write(self.cs_pin, 1)  # type: ignore[attr-defined]

    def read_busy(self) -> None:
        debug("e-Paper busy")
        self.send_command(0x71)
        busy = epdconfig.digital_read(self.busy_pin)  # type: ignore[attr-defined]
        while busy == 0:
            self.send_command(0x71)
            busy = epdconfig.digital_read(self.busy_pin)  # type: ignore[attr-defined]
        epdconfig.delay_ms(200)  # type: ignore[attr-defined]

    def init(self) -> int:
        if epdconfig.module_init() != 0:  # type: ignore[attr-defined]
            return -1
        # EPD hardware init start
        self.reset()

        self.send_command(0x01)  # POWER SETTING
        self.send_data(0x07)
        self.send_data(0x07)  # VGH=20V,VGL=-20V
        self.send_data(0x3F)  # VDH=15V
        self.send_data(0x3F)  # VDL=-15V

        self.send_command(0x04)  # POWER ON
        epdconfig.delay_ms(100)  # type: ignore[attr-defined]
        self.read_busy()

        self.send_command(0x00)  # PANEL SETTING
        self.send_data(0x1F)  # KW-3f   KWR-2F	BWROTP 0f	BWOTP 1f

        self.send_command(0x61)  # tres
        self.send_data(0x03)  # source 800
        self.send_data(0x20)
        self.send_data(0x01)  # gate 480
        self.send_data(0xE0)

        self.send_command(0x15)
        self.send_data(0x00)

        self.send_command(0x50)  # VCOM AND DATA INTERVAL SETTING
        self.send_data(0x10)
        self.send_data(0x07)

        self.send_command(0x60)  # TCON SETTING
        self.send_data(0x22)

        # EPD hardware init end
        return 0

    def getbuffer(self, image: Image) -> list[int]:
        buf = [0xFF] * (int(self.width / 8) * self.height)
        image_monocolor = image.convert("1")
        imwidth, imheight = image_monocolor.size
        pixels = image_monocolor.load()
        if imwidth == self.width and imheight == self.height:
            debug("Vertical")
            for y in range(imheight):
                for x in range(imwidth):
                    # Set the bits for the column of pixels at the current position.
                    if pixels[x, y] == 0:
                        buf[int((x + y * self.width) / 8)] &= ~(0x80 >> (x % 8))
        elif imwidth == self.height and imheight == self.width:
            debug("Horizontal")
            for y in range(imheight):
                for x in range(imwidth):
                    new_x = y
                    new_y = self.height - x - 1
                    if pixels[x, y] == 0:
                        buf[int((new_x + new_y * self.width) / 8)] &= ~(0x80 >> (y % 8))
        return buf

    def display(self, image: Image) -> None:
        self.send_command(0x13)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(~image[i])  # type: ignore[index]

        self.send_command(0x12)
        epdconfig.delay_ms(100)  # type: ignore[attr-defined]
        self.read_busy()

    def clear(self) -> None:
        self.send_command(0x10)
        for _ in range(0, int(self.width * self.height / 8)):
            self.send_data(0x00)

        self.send_command(0x13)
        for _ in range(0, int(self.width * self.height / 8)):
            self.send_data(0x00)

        self.send_command(0x12)
        epdconfig.delay_ms(100)  # type: ignore[attr-defined]
        self.read_busy()

    def sleep(self) -> None:
        self.send_command(0x02)  # POWER_OFF
        self.read_busy()

        self.send_command(0x07)  # DEEP_SLEEP
        self.send_data(0xA5)

    @staticmethod
    def dev_exit() -> None:
        epdconfig.module_exit()  # type: ignore[attr-defined]
