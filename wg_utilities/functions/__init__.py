"""Useful functions."""

from __future__ import annotations

from ._functions import chunk_list, flatten_dict, try_float
from .datetime_helpers import DTU, DatetimeFixedUnit, utcnow
from .file_management import force_mkdir, user_data_dir
from .json import process_list, set_nested_value, traverse_dict
from .processes import run_cmd
from .string_manipulation import cleanse_string

__all__ = [
    "chunk_list",
    "flatten_dict",
    "try_float",
    "utcnow",
    "DTU",
    "DatetimeFixedUnit",
    "force_mkdir",
    "user_data_dir",
    "set_nested_value",
    "run_cmd",
    "cleanse_string",
    "process_list",
    "traverse_dict",
]

try:
    __all__.append(
        "get_nsmap",
    )
except ImportError as _exc:  # pragma: no cover
    if str(_exc) == "No module named 'lxml'":
        pass
