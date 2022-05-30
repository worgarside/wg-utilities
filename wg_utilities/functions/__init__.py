"""Useful functions"""

from .datetime_helpers import utcnow
from .file_management import user_data_dir, force_mkdir
from .processes import run_cmd
from .string_manipulation import cleanse_string
from .xml import get_nsmap
from .json import set_nested_value
