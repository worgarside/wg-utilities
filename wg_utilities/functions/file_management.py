"""Functions for specifically managing files and directories"""

from os import environ, getenv
from os.path import dirname
from pathlib import Path
from sys import platform
from typing import Optional, Union


def user_data_dir(
    *, project_name: str = "WgUtilities", file_name: Optional[str] = None
) -> Path:
    """Get OS specific data directory path

    Typical user data directories are:
        macOS:    ~/Library/Application Support
        Unix:     ~/.local/share   # or in $XDG_DATA_HOME, if defined
        Win 10:   C:\\Users\\<username>\\AppData\\Local

    For Unix, we follow the XDG spec and support $XDG_DATA_HOME if defined.

    Args:
        project_name (str): the name of the project which the utils are running in
        file_name (Optional[str]): file to be fetched from the data dir

    Returns:
        str: full path to the user-specific data dir
    """

    # get os specific path
    if platform.startswith("win"):
        os_path = environ["LOCALAPPDATA"]
    elif platform.startswith("darwin"):
        os_path = "~/Library/Application Support"
    else:
        # linux
        os_path = getenv("XDG_DATA_HOME", "~/.local/share")

    path = Path(os_path) / project_name

    if file_name:
        return path.expanduser() / file_name

    return path.expanduser()


def force_mkdir(
    target_path: Union[str, Path], path_is_file: bool = False
) -> Union[str, Path]:
    """Creates all directories needed for the given path

    Args:
        target_path (str): the path to the directory which needs to be created
        path_is_file (bool): flag for whether the path is for a file, in which case
         the final part of the path will not be created

    Returns:
        str: directory_path that was passed in
    """
    if path_is_file:
        Path(dirname(target_path)).mkdir(exist_ok=True, parents=True)
    else:
        Path(target_path).mkdir(exist_ok=True, parents=True)

    return target_path
