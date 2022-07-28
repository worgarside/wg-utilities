"""Useful functions"""

from ._functions import chunk_list, flatten_dict, try_float
from .datetime_helpers import utcnow
from .file_management import force_mkdir, user_data_dir
from .json import process_list, set_nested_value, traverse_dict
from .processes import run_cmd
from .string_manipulation import cleanse_string

__all__ = [
    "chunk_list",
    "flatten_dict",
    "try_float",
    "utcnow",
    "force_mkdir",
    "user_data_dir",
    "set_nested_value",
    "run_cmd",
    "cleanse_string",
    "process_list",
    "traverse_dict",
]

try:
    from .xml import get_nsmap

    __all__.append(
        "get_nsmap",
    )
except ImportError as _exc:
    if str(_exc) == "No module named 'lxml'":
        pass
