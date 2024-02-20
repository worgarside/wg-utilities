from __future__ import annotations

from functools import lru_cache
from typing import Self

from wg_utilities.functions.subclasses import subclasses_recursive


class WGUtilitiesError(Exception):
    """Base class for all exceptions raised by wg_utilities."""

    @classmethod
    @lru_cache
    def subclasses(cls) -> list[type[Self]]:
        return list(subclasses_recursive(cls))


class BadDefinitionError(WGUtilitiesError):
    """Raised when some kind of definition is invalid."""


__all__ = ["WGUtilitiesError", "BadDefinitionError"]
