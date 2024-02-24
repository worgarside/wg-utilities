"""Custom exception types."""

from __future__ import annotations

from ._deprecated import on_exception, send_exception_to_home_assistant
from ._exception import BadDefinitionError, BadUsageError, NotFoundError, WGUtilitiesError

__all__ = [
    "on_exception",
    "send_exception_to_home_assistant",
    "WGUtilitiesError",
    "BadDefinitionError",
    "BadUsageError",
    "NotFoundError",
]
