from __future__ import annotations


class WGUtilitiesError(Exception):
    """Base class for all exceptions raised by wg_utilities."""


class BadDefinitionError(WGUtilitiesError):
    """Raised when some kind of definition is invalid."""


__all__ = ["WGUtilitiesError", "BadDefinitionError"]
