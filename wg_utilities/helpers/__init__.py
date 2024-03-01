from __future__ import annotations

from typing import Any, Literal, Never

from . import mixin


class Sentinel:
    """Dummy value for tripping conditions, breaking loops, all sorts!"""

    def __bool__(self) -> Literal[False]:
        """Always False, so that it can be used as a sentinel value."""
        return False

    def __call__(self, *_: Any, **__: Any) -> None:
        """Do nothing when called."""

    def __eq__(self, other: Any) -> bool:
        """Return True if the other value is also a Sentinel."""
        return isinstance(other, Sentinel)

    def __hash__(self) -> int:
        """Return a hash of the class name."""
        return hash(self.__class__.__name__)

    def __iter__(self) -> Iterator:
        """Return an iterator that will always raise StopIteration."""
        return self.Iterator()

    def __ne__(self, other: Any) -> bool:
        """Return False if the other value is also a Sentinel."""
        return not isinstance(other, Sentinel)

    def __repr__(self) -> str:
        """Return the class name."""
        return self.__class__.__name__

    class Iterator:
        """An iterator that will always raise StopIteration."""

        def __iter__(self) -> Sentinel.Iterator:
            """Return an iterator that will always raise StopIteration."""
            return self

        def __next__(self) -> Never:
            """Always raise StopIteration."""
            raise StopIteration


__all__ = ["mixin", "Sentinel"]
