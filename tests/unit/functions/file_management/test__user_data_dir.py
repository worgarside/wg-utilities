"""Unit Tests for `wg_utilities.functions.file_management.user_data_dir`."""
from __future__ import annotations

from os import environ
from pathlib import Path
from unittest.mock import patch

from pytest import mark

from wg_utilities.functions import user_data_dir


@patch.dict(
    environ,
    {
        "LOCALAPPDATA": "C:/Users/test/AppData/Local",
        "XDG_DATA_HOME": "/home/will/.local/share",
    },
)
@mark.parametrize(
    "platform,expected",
    [
        ("windows", "C:/Users/test/AppData/Local/WgUtilities"),
        ("darwin", "Library/Application Support/WgUtilities"),
        ("linux", "/home/will/.local/share/WgUtilities"),
    ],
)
def test_correct_value_returned_per_system(platform: str, expected: str) -> None:
    """Test that the correct value is returned for each OS."""
    assert str(user_data_dir(_platform=platform)).endswith(expected)


@patch.dict(
    environ,
    {
        "LOCALAPPDATA": "C:/Users/test/AppData/Local",
        "XDG_DATA_HOME": "/home/will/.local/share",
    },
)
@mark.parametrize(
    "platform,project_name,expected",
    [
        (
            "windows",
            "windows_project",
            "C:/Users/test/AppData/Local/windows_project",
        ),
        (
            "darwin",
            "macos_project",
            "/Library/Application Support/macos_project",
        ),
        ("linux", "linux_project", "/home/will/.local/share/linux_project"),
    ],
)
def test_project_name_processed_correctly(
    platform: str, project_name: str, expected: str
) -> None:
    """Test that the value passed in `project_name` is added to the path."""

    actual = user_data_dir(_platform=platform, project_name=project_name)

    assert project_name in str(actual)
    assert str(actual).endswith(expected)


@patch.dict(
    environ,
    {
        "LOCALAPPDATA": "C:/Users/test/AppData/Local",
        "XDG_DATA_HOME": "/home/will/.local/share",
    },
)
@mark.parametrize(
    "platform,file_name,expected",
    [
        (
            "windows",
            "windows_file",
            Path("C:/Users/test/AppData/Local/WgUtilities/windows_file"),
        ),
        (
            "darwin",
            "macos_file",
            Path("/Library/Application Support/WgUtilities/macos_file"),
        ),
        ("linux", "linux_file", Path("/home/will/.local/share/WgUtilities/linux_file")),
    ],
)
def test_file_name_processed_correctly(
    platform: str, file_name: str, expected: Path
) -> None:
    """Test that the value passed in `project_name` is added to the path."""

    with patch(
        "wg_utilities.functions.file_management.force_mkdir",
        lambda target_path, path_is_file: target_path,
    ):
        actual = user_data_dir(
            file_name=file_name,
            _platform=platform,
        )

    assert str(actual).endswith(file_name)
    assert str(actual).endswith(str(expected))
