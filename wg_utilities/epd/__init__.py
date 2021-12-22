"""Drivers obtained from https://github.com/waveshare/e-Paper"""
from logging import Formatter, getLogger, DEBUG, StreamHandler
from sys import stdout

from .epd7in5_v2 import EPD_WIDTH, EPD_HEIGHT
from .epdconfig import TEST_MODE, implementation

_FORMATTER = Formatter(
    "%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s", "%Y-%m-%d %H:%M:%S"
)

_SH = StreamHandler(stdout)
_SH.setFormatter(_FORMATTER)

_LOGGER = getLogger(__name__)
_LOGGER.setLevel(DEBUG)
_LOGGER.addHandler(_SH)

if not TEST_MODE:
    from .epd7in5_v2 import EPD

    FRAME_DELAY = 120
else:
    from .epd7in5_v2 import EPD as EPD_ORIG

    _LOGGER.warning("Unable to import E-Paper Driver, running in test mode")
    FRAME_DELAY = 0

    # pylint: disable=too-few-public-methods
    class EPD:
        """Dynamically built class to mirror the functionality of the EPD on devices
        which don't support it"""

    for method in dir(EPD_ORIG):
        if not method.startswith("_"):
            setattr(EPD, method, lambda *a, **k: None)
