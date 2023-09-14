"""Useful functions."""

from __future__ import annotations

from ._functions import chunk_list, flatten_dict, try_float
from .datetime_helpers import DTU, DatetimeFixedUnit, utcnow
from .decorators import backoff
from .file_management import force_mkdir, user_data_dir
from .json import process_list, set_nested_value, traverse_dict
from .processes import run_cmd
from .string_manipulation import cleanse_string

__all__ = [
    "chunk_list",
    "cleanse_string",
    "DTU",
    "DatetimeFixedUnit",
    "backoff",
    "flatten_dict",
    "force_mkdir",
    "process_list",
    "run_cmd",
    "set_nested_value",
    "traverse_dict",
    "try_float",
    "user_data_dir",
    "utcnow",
]

try:
    __all__.append(
        "get_nsmap",
    )
except ImportError as _exc:  # pragma: no cover
    if str(_exc) == "No module named 'lxml'":
        pass
