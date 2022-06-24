"""Useful functions"""

from ._functions import chunk_list, flatten_dict, try_float
from .datetime_helpers import utcnow
from .file_management import force_mkdir, user_data_dir
from .json import process_list, set_nested_value, traverse_dict
from .processes import run_cmd
from .string_manipulation import cleanse_string
from .xml import get_nsmap

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
    "get_nsmap",
    "process_list",
    "traverse_dict",
]
