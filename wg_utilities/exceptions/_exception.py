from __future__ import annotations

from functools import lru_cache
from typing import Self

from wg_utilities.functions.subclasses import subclasses_recursive


class WGUtilitiesError(Exception):
    """Base class for all exceptions raised by wg_utilities."""

    @classmethod
    @lru_cache
    def subclasses(cls) -> list[type[Self]]:
        """Return a list of all subclasses of this error, cached for performance."""
        return list(subclasses_recursive(cls))


class BadDefinitionError(WGUtilitiesError):
    """Raised when some kind of definition is invalid."""


class BadUsageError(WGUtilitiesError):
    """Raised when something is used incorrectly."""


class NotFoundError(WGUtilitiesError):
    """Raised when something is not found."""


__all__ = ["WGUtilitiesError", "BadDefinitionError", "BadUsageError", "NotFoundError"]
