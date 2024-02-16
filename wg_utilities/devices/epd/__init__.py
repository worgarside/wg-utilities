"""Drivers obtained from https://github.com/waveshare/e-Paper/."""

from __future__ import annotations

from logging import DEBUG, Formatter, StreamHandler, getLogger
from sys import stdout

from .epd7in5_v2 import EPD_HEIGHT, EPD_WIDTH
from .epdconfig import TEST_MODE, implementation

_FORMATTER = Formatter(
    "%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s",
    "%Y-%m-%d %H:%M:%S",
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

    class EPD:  # type: ignore[no-redef]
        """Mirror the functionality of the EPD on devices which don't support it."""

    for method in dir(EPD_ORIG):
        if not method.startswith("_"):
            setattr(EPD, method, lambda *_, **__: None)

__all__ = ["EPD", "EPD_HEIGHT", "EPD_WIDTH", "implementation", "FRAME_DELAY"]
