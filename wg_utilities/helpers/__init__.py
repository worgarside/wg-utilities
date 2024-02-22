from __future__ import annotations

from . import mixin


class Sentinel:
    """Dummy value for tripping conditions, breaking loops, all sorts!"""


__all__ = ["mixin", "Sentinel"]
