from __future__ import annotations

from typing import Literal

from . import mixin


class Sentinel:
    """Dummy value for tripping conditions, breaking loops, all sorts!"""

    def __bool__(self) -> Literal[False]:
        """Always False, so that it can be used as a sentinel value."""
        return False

    def __iter__(self) -> Iterator:
        """Return an iterator that will always raise StopIteration."""
        return self.Iterator()

    class Iterator:
        """An iterator that will always raise StopIteration."""

        def __iter__(self) -> Sentinel.Iterator:
            """Return an iterator that will always raise StopIteration."""
            return self

        def __next__(self) -> Sentinel:
            """Always raise StopIteration."""
            raise StopIteration


__all__ = ["mixin", "Sentinel"]
